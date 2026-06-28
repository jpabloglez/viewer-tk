from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Literal

import numpy as np
from PIL import Image

from ..models.base import ImageVolume
from ..models.dicom import DicomVolume
from ..models.nifti import NiftiVolume
from ..utils.normalization import (
    WINDOW_PRESETS,
    apply_colormap,
    apply_window_level,
    normalize_min_max,
)
from ..utils.prefs import load_prefs, save_prefs
from ..utils.recent import add_recent, load_recent
from ..utils.strings import (
    APP_TITLE,
    MSG_LOAD_IMAGE_FIRST,
    MSG_NO_IMAGE_RENDERED,
    MSG_NO_METADATA,
    SHORTCUTS,
    STATUS_LOAD_FAILED,
    STATUS_MEASURE_SECOND,
    STATUS_MEASURE_START,
    STATUS_READY,
    msg_load_failed,
    status_loaded_dicom,
    status_loaded_nifti,
    status_loading_dicom,
    status_loading_nifti,
    status_measure_mm,
    status_measure_px,
    status_saved,
    status_scanning_dicom,
)
from ..utils.theme import apply_theme
from ..views.canvas import ImageCanvas
from ..views.histogram import HistogramWindow
from ..views.info_bar import InfoBar
from ..views.menubar import MenuBar
from ..views.metadata import MetadataWindow
from ..views.multi_canvas import MultiAxisCanvas
from ..views.toolbar import Toolbar

logger = logging.getLogger(__name__)

_AXIS_LABEL = {0: "Sag", 1: "Cor", 2: "Ax"}


class ViewerController:
    """Main controller — wires model, views, and user actions."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)

        self._model: ImageVolume | None = None
        self._current_slice = 0
        self._current_axis = 2  # axial by default
        self._axis_slices: dict[int, int] = {0: 0, 1: 0, 2: 0}
        self._window_center: float | None = None
        self._window_width: float | None = None
        self._is_multi_axis = False
        self._loaded_path: str | None = None
        self._invert = False
        self._current_volume = 0
        # Per-axis raw slice cache for cursor readout and histogram
        self._last_raw_per_axis: dict[int, np.ndarray] = {}

        # Background-load → UI marshalling. Worker threads MUST NOT call root.after()
        # directly: Tcl is not thread-safe and cross-thread after() is silently dropped
        # (notably on Tcl 9.0). Instead they push messages onto this queue and the main
        # thread drains it via a poller scheduled with after() from the main thread.
        self._load_queue: queue.Queue = queue.Queue()
        self._polling = False

        # Load persisted preferences before building UI
        self._prefs = load_prefs()
        self._colormap: str = self._prefs.get("colormap", "gray")
        apply_theme(root, "dark")

        # --- build UI ---
        self._toolbar = Toolbar(root)
        self._toolbar.pack(fill=tk.X, padx=4, pady=(4, 0))

        self._canvas = ImageCanvas(root)
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._multi_canvas: MultiAxisCanvas | None = None

        self._info_bar = InfoBar(root)
        self._info_bar.pack(fill=tk.X, padx=4)

        self._slider = tk.Scale(
            root, from_=0, to=0, orient=tk.HORIZONTAL,
            command=self._on_slider,
        )
        self._slider.pack(fill=tk.X, padx=4, pady=(0, 4))

        # Volume slider for 4D NIfTI — hidden until needed
        self._volume_slider = tk.Scale(
            root, from_=0, to=0, orient=tk.HORIZONTAL, label="Volume",
            command=self._on_volume_slider,
        )
        # not packed yet

        # Status bar
        self._status_var = tk.StringVar(value=STATUS_READY)
        self._status_bar = tk.Label(
            root, textvariable=self._status_var,
            bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=4,
        )
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Progress bar — shown only during DICOM header scan, hidden otherwise
        self._progress_bar = ttk.Progressbar(
            root, orient=tk.HORIZONTAL, mode="determinate",
        )
        # not packed yet

        # --- menu bar ---
        self._menubar = MenuBar(root)
        self._menubar.on_open_dir = self.open_directory
        self._menubar.on_open_file = self.open_file
        self._menubar.on_exit = root.destroy
        self._menubar.on_metadata = self._show_metadata
        self._menubar.on_reset_zoom = self._reset_zoom
        self._menubar.on_window_preset = self._on_window_preset
        self._menubar.on_histogram = self._show_histogram
        self._menubar.on_open_recent = self._on_open_recent
        self._menubar.on_save_view = self.save_view
        self._menubar.on_show_shortcuts = self._show_shortcuts

        # Populate recent files on startup
        self._menubar.refresh_recent(load_recent())

        # --- toolbar callbacks ---
        self._toolbar.on_open_dir = self.open_directory
        self._toolbar.on_open_file = self.open_file
        self._toolbar.on_metadata = self._show_metadata
        self._toolbar.on_histogram = self._show_histogram
        self._toolbar.on_window_preset = self._on_window_preset
        self._toolbar.on_colormap = self._on_colormap
        self._toolbar.on_window_manual = self._on_window_manual
        self._toolbar.on_zoom_fit = self._canvas.fit_view
        self._toolbar.on_zoom_actual = self._canvas.actual_size
        self._toolbar.on_auto_wl = self._on_auto_wl
        self._toolbar.on_toggle_invert = self._on_toggle_invert
        self._toolbar.on_toggle_measure = self._on_toggle_measure
        # Sync toolbar colormap dropdown to loaded pref
        self._toolbar.set_colormap(self._colormap)

        # --- cursor, W/L drag, and measurement ---
        self._canvas.on_cursor_move = self._on_cursor_move
        self._canvas.on_wl_drag = self._on_canvas_wl_drag
        self._canvas.on_measure_update = self._on_measure_update

        # --- key bindings ---
        root.bind("<Control-s>", lambda e: self.save_view())
        root.bind("<Left>", lambda e: self._step(-1))
        root.bind("<Right>", lambda e: self._step(1))
        root.bind("<Home>", lambda e: self._goto(0))
        root.bind("<End>", lambda e: self._goto_end())
        root.bind("<Control-o>", lambda e: self.open_directory())
        root.bind("<Control-O>", lambda e: self.open_file())
        root.bind("<Control-m>", lambda e: self._show_metadata())
        root.bind("<Control-h>", lambda e: self._show_histogram())
        root.bind("<Control-0>", lambda e: self._reset_zoom())
        root.bind("<Control-q>", lambda e: root.destroy())
        root.bind("?", lambda e: self._show_shortcuts())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_view(self) -> None:
        """Save the current rendered view to a PNG/JPEG file."""
        if self._model is None:
            messagebox.showinfo("Info", MSG_LOAD_IMAGE_FIRST)
            return
        axis = 2 if self._is_multi_axis else self._current_axis
        raw = self._last_raw_per_axis.get(axis)
        if raw is None:
            messagebox.showinfo("Info", MSG_NO_IMAGE_RENDERED)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("JPEG image", "*.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
            title="Save current view",
        )
        if not path:
            return
        try:
            self._apply_pipeline(raw).save(path)
            self._status_var.set(status_saved(path))
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save image:\n{exc}")

    def open_directory(self, directory: str | None = None) -> None:
        if directory is None:
            directory = filedialog.askdirectory()
        if not directory:
            return
        self._toolbar.set_loading(True)
        self._status_var.set(status_loading_dicom(directory))
        self._show_progress_bar(mode="determinate")
        self._start_poll()
        threading.Thread(
            target=self._load_directory_bg, args=(directory,), daemon=True
        ).start()

    def open_file(self, file_path: str | None = None) -> None:
        if file_path is None:
            file_path = filedialog.askopenfilename(
                filetypes=[("NIfTI files", "*.nii *.nii.gz"), ("All files", "*.*")]
            )
        if not file_path:
            return
        self._toolbar.set_loading(True)
        self._status_var.set(status_loading_nifti(file_path))
        self._show_progress_bar(mode="indeterminate")
        self._start_poll()
        threading.Thread(
            target=self._load_file_bg, args=(file_path,), daemon=True
        ).start()

    # ------------------------------------------------------------------
    # Background loading
    #
    # Worker threads communicate ONLY via self._load_queue; the main-thread
    # poller (_poll_load_queue) drains it and invokes the UI handlers.
    # ------------------------------------------------------------------

    def _start_poll(self) -> None:
        if not self._polling:
            self._polling = True
            self.root.after(60, self._poll_load_queue)

    def _poll_load_queue(self) -> None:
        try:
            while True:
                msg = self._load_queue.get_nowait()
                self._dispatch_load_msg(msg)
        except queue.Empty:
            pass
        if self._polling:
            self.root.after(60, self._poll_load_queue)

    def _dispatch_load_msg(self, msg: tuple) -> None:
        kind = msg[0]
        if kind == "progress":
            self._on_load_progress(msg[1], msg[2])
        elif kind == "loaded_dir":
            self._polling = False
            self._on_directory_loaded(msg[1], msg[2])
        elif kind == "loaded_file":
            self._polling = False
            self._on_file_loaded(msg[1], msg[2])
        elif kind == "error":
            self._polling = False
            self._on_load_error(msg[1])

    def _on_load_error(self, path: str) -> None:
        messagebox.showerror("Error", msg_load_failed(path))
        self._toolbar.set_loading(False)
        self._hide_progress_bar()
        self._status_var.set(STATUS_LOAD_FAILED)

    def _load_directory_bg(self, directory: str) -> None:
        try:
            model = DicomVolume()

            def _progress(done: int, total: int) -> None:
                self._load_queue.put(("progress", done, total))

            model.load(directory, progress_callback=_progress)
            self._load_queue.put(("loaded_dir", model, directory))
        except Exception:
            logger.exception("Failed to load DICOM directory")
            self._load_queue.put(("error", directory))

    def _on_directory_loaded(self, model: DicomVolume, path: str) -> None:
        self._model = model
        self._loaded_path = path
        self._current_slice = 0
        self._current_volume = 0
        self._last_raw_per_axis = {}
        self._canvas.set_measure_mode(False)
        self._teardown_multi_axis()
        self._teardown_volume_slider()
        model.get_slice(0)
        center, width = model.get_window_defaults()
        self._window_center = center
        self._window_width = width
        self._update_slider()
        self._render_slice()
        self._update_info()
        self._toolbar.set_loading(False)
        self._hide_progress_bar()
        self._status_var.set(status_loaded_dicom(path, model.num_slices()))
        add_recent(path, "dir")
        self._menubar.refresh_recent(load_recent())

    def _load_file_bg(self, file_path: str) -> None:
        try:
            model = NiftiVolume()
            model.load(file_path)
            self._load_queue.put(("loaded_file", model, file_path))
        except Exception:
            logger.exception("Failed to load NIfTI file")
            self._load_queue.put(("error", file_path))

    def _on_file_loaded(self, model: NiftiVolume, path: str) -> None:
        self._model = model
        self._loaded_path = path
        self._window_center = None
        self._window_width = None
        self._current_slice = 0
        self._current_volume = 0
        self._last_raw_per_axis = {}
        self._canvas.set_measure_mode(False)
        self._axis_slices = {
            ax: model.num_slices(ax) // 2 for ax in (0, 1, 2)
        }
        self._setup_multi_axis()
        if model.num_volumes() > 1:
            self._setup_volume_slider(model.num_volumes())
        else:
            self._teardown_volume_slider()
        self._update_slider()
        self._render_slice()
        self._update_info()
        self._toolbar.set_loading(False)
        self._hide_progress_bar()
        x, y, z = (model.num_slices(ax) for ax in (0, 1, 2))
        self._status_var.set(status_loaded_nifti(path, x, y, z))
        add_recent(path, "file")
        self._menubar.refresh_recent(load_recent())

    # ------------------------------------------------------------------
    # Multi-axis management
    # ------------------------------------------------------------------

    def _setup_multi_axis(self) -> None:
        """Switch to multi-axis view for NIfTI volumes."""
        if not isinstance(self._model, NiftiVolume):
            return
        self._canvas.pack_forget()
        self._slider.pack_forget()

        if self._multi_canvas is None:
            self._multi_canvas = MultiAxisCanvas(self.root)
            self._multi_canvas.on_slice_change = self._on_multi_axis_slider
            self._multi_canvas.on_cursor_move = self._on_multi_cursor_move
            self._multi_canvas.on_crosshair_click = self._on_crosshair_click
        self._multi_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4,
                                before=self._info_bar)
        self._is_multi_axis = True

        for axis in (0, 1, 2):
            num = self._model.num_slices(axis)
            self._multi_canvas.configure_axis(axis, num, self._axis_slices[axis])

    def _teardown_multi_axis(self) -> None:
        if self._multi_canvas is not None:
            self._multi_canvas.pack_forget()
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4,
                          before=self._info_bar)
        self._slider.pack(fill=tk.X, padx=4, pady=(0, 4), before=self._status_bar)
        self._is_multi_axis = False

    def _setup_volume_slider(self, n_volumes: int) -> None:
        self._volume_slider.config(from_=0, to=n_volumes - 1)
        self._volume_slider.set(0)
        self._volume_slider.pack(fill=tk.X, padx=4, pady=(0, 2), before=self._info_bar)

    def _teardown_volume_slider(self) -> None:
        self._volume_slider.pack_forget()

    def _on_volume_slider(self, value) -> None:
        idx = int(float(value))
        if idx == self._current_volume:
            return
        self._current_volume = idx
        self._render_slice()
        self._update_info()

    def _on_multi_axis_slider(self, axis: int, index: int) -> None:
        self._axis_slices[axis] = index
        self._render_single_axis(axis, index)
        self._update_crosshair()
        self._update_info()

    # ------------------------------------------------------------------
    # Single-axis slider (DICOM mode)
    # ------------------------------------------------------------------

    def _update_slider(self) -> None:
        if self._model is None:
            return
        if self._is_multi_axis:
            return
        max_val = self._model.num_slices(self._current_axis) - 1
        self._slider.config(from_=0, to=max_val)
        self._slider.set(self._current_slice)

    def _on_slider(self, value) -> None:
        idx = int(float(value))
        if idx == self._current_slice:
            return
        self._current_slice = idx
        self._render_slice()
        self._update_info()

    def _step(self, delta: int) -> None:
        if self._model is None:
            return
        if self._is_multi_axis:
            axis = 2
            new = self._axis_slices[axis] + delta
            if 0 <= new < self._model.num_slices(axis):
                self._axis_slices[axis] = new
                self._multi_canvas.set_slice(axis, new)
                self._render_single_axis(axis, new)
                self._update_crosshair()
                self._update_info()
            return
        new = self._current_slice + delta
        if 0 <= new < self._model.num_slices(self._current_axis):
            self._current_slice = new
            self._slider.set(new)
            self._render_slice()
            self._update_info()

    def _goto(self, index: int) -> None:
        if self._model is None:
            return
        self._current_slice = max(0, min(index, self._model.num_slices(self._current_axis) - 1))
        self._slider.set(self._current_slice)
        self._render_slice()
        self._update_info()

    def _goto_end(self) -> None:
        if self._model is None:
            return
        self._goto(self._model.num_slices(self._current_axis) - 1)

    # ------------------------------------------------------------------
    # Render pipeline
    # ------------------------------------------------------------------

    def _render_slice(self) -> None:
        """Unified render: model.get_slice -> normalize -> colormap -> display."""
        if self._model is None:
            return

        if self._is_multi_axis and isinstance(self._model, NiftiVolume):
            self._render_all_axes()
            return

        raw = self._model.get_slice(
            self._current_slice, self._current_axis, volume=self._current_volume
        )
        self._last_raw_per_axis[self._current_axis] = raw
        img = self._apply_pipeline(raw)
        self._canvas.display(img)
        self._toolbar.update_zoom_label(self._canvas.zoom_percent)

    def _render_all_axes(self) -> None:
        for axis in (0, 1, 2):
            self._render_single_axis(axis, self._axis_slices[axis])
        self._update_crosshair()

    def _render_single_axis(self, axis: int, index: int) -> None:
        raw = self._model.get_slice(index, axis, volume=self._current_volume)
        self._last_raw_per_axis[axis] = raw
        img = self._apply_pipeline(raw)
        self._multi_canvas.display(axis, img, slice_idx=index)

    def _apply_pipeline(self, raw_data) -> Image.Image:
        """Normalize -> window/level -> invert -> colormap -> PIL Image."""
        if self._window_center is not None and self._window_width is not None:
            uint8 = apply_window_level(raw_data, self._window_center, self._window_width)
        else:
            uint8 = normalize_min_max(raw_data)
        if self._invert:
            uint8 = 255 - uint8
        rgb = apply_colormap(uint8, self._colormap)
        return Image.fromarray(rgb)

    # ------------------------------------------------------------------
    # Info & metadata
    # ------------------------------------------------------------------

    def _update_info(self) -> None:
        if self._model is None:
            return
        info = self._model.get_info_summary()
        if self._is_multi_axis:
            for axis, label in ((2, "Axial"), (0, "Sagittal"), (1, "Coronal")):
                total = self._model.num_slices(axis)
                info[label] = f"{self._axis_slices[axis] + 1} / {total}"
        else:
            total = self._model.num_slices(self._current_axis)
            info["Slice"] = f"{self._current_slice + 1} / {total}"
        self._info_bar.update_info(info)

    def _show_metadata(self) -> None:
        if self._model is None:
            messagebox.showinfo("Info", MSG_LOAD_IMAGE_FIRST)
            return
        meta = self._model.get_metadata()
        if meta is None:
            messagebox.showinfo("Info", MSG_NO_METADATA)
            return
        win = tk.Toplevel(self.root)
        MetadataWindow(win, meta)

    def _show_histogram(self) -> None:
        if self._model is None:
            messagebox.showinfo("Info", MSG_LOAD_IMAGE_FIRST)
            return
        if self._is_multi_axis:
            axis = 2
            raw = self._last_raw_per_axis.get(axis)
            if raw is None:
                raw = self._model.get_slice(
                    self._axis_slices[axis], axis, volume=self._current_volume
                )
                self._last_raw_per_axis[axis] = raw
            title = "Axial"
        else:
            raw = self._last_raw_per_axis.get(self._current_axis)
            if raw is None:
                raw = self._model.get_slice(
                    self._current_slice, self._current_axis, volume=self._current_volume
                )
                self._last_raw_per_axis[self._current_axis] = raw
            title = f"Slice {self._current_slice + 1}"
        win = tk.Toplevel(self.root)
        HistogramWindow(win, raw, title=title)

    # ------------------------------------------------------------------
    # Toolbar callbacks
    # ------------------------------------------------------------------

    def _reset_zoom(self) -> None:
        if self._is_multi_axis and self._multi_canvas is not None:
            self._multi_canvas.reset_view()
        else:
            self._canvas.reset_view()

    def _on_window_preset(self, name: str) -> None:
        if name == "Auto":
            self._window_center = None
            self._window_width = None
        else:
            self._window_center, self._window_width = WINDOW_PRESETS[name]
        self._toolbar.sync_window_sliders(self._window_center, self._window_width)
        self._render_slice()

    def _on_window_manual(self, center: float, width: float) -> None:
        self._window_center = center
        self._window_width = width
        self._render_slice()

    def _on_colormap(self, cmap: str) -> None:
        self._colormap = cmap
        self._prefs["colormap"] = cmap
        save_prefs(self._prefs)
        self._render_slice()

    def _on_canvas_wl_drag(self, dcenter: float, dwidth: float) -> None:
        """Right-click drag on canvas adjusts window/level in real time."""
        if self._window_center is None or self._window_width is None:
            raw = self._last_raw_per_axis.get(self._current_axis)
            if raw is None:
                return
            mn, mx = float(np.min(raw)), float(np.max(raw))
            self._window_center = (mn + mx) / 2.0
            self._window_width = max(1.0, mx - mn)
        self._window_center = max(-4096.0, min(self._window_center + dcenter, 4096.0))
        self._window_width = max(1.0, min(self._window_width + dwidth, 8192.0))
        self._toolbar.sync_window_sliders(self._window_center, self._window_width)
        self._render_slice()

    def _on_auto_wl(self) -> None:
        """Set W/L from 2nd–98th percentile of the current slice."""
        axis = 2 if self._is_multi_axis else self._current_axis
        raw = self._last_raw_per_axis.get(axis)
        if raw is None:
            return
        p2, p98 = float(np.percentile(raw, 2)), float(np.percentile(raw, 98))
        width = max(1.0, p98 - p2)
        self._window_center = (p2 + p98) / 2.0
        self._window_width = width
        self._toolbar.sync_window_sliders(self._window_center, self._window_width)
        self._render_slice()

    def _on_toggle_invert(self, active: bool) -> None:
        self._invert = active
        self._render_slice()

    def _on_toggle_measure(self, active: bool) -> None:
        self._canvas.set_measure_mode(active)
        self._status_var.set(STATUS_MEASURE_START if active else STATUS_READY)

    def _on_measure_update(self, pts: list[tuple[int, int]]) -> None:
        if len(pts) == 1:
            self._status_var.set(STATUS_MEASURE_SECOND)
        elif len(pts) == 2:
            spacing = self._model.get_pixel_spacing() if self._model else None
            (x1, y1), (x2, y2) = pts
            if spacing:
                dx = (x2 - x1) * spacing[1]
                dy = (y2 - y1) * spacing[0]
                dist = (dx ** 2 + dy ** 2) ** 0.5
                self._status_var.set(status_measure_mm(dist))
            else:
                dist_px = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                self._status_var.set(status_measure_px(dist_px))

    def _on_crosshair_click(self, clicked_axis: int, img_x: int, img_y: int) -> None:
        """Clicking in one NIfTI panel navigates the other two to the same voxel."""
        if not isinstance(self._model, NiftiVolume):
            return
        X = self._model.num_slices(0)
        Y = self._model.num_slices(1)
        Z = self._model.num_slices(2)

        def _clamp(v: int, size: int) -> int:
            return max(0, min(v, size - 1))

        if clicked_axis == 2:    # axial:   img_x→vox_x(sag), (Y-1)-img_y→vox_y(cor)
            updates = {0: _clamp(img_x, X), 1: _clamp((Y - 1) - img_y, Y)}
        elif clicked_axis == 0:  # sagittal: img_x→vox_y(cor), (Z-1)-img_y→vox_z(ax)
            updates = {1: _clamp(img_x, Y), 2: _clamp((Z - 1) - img_y, Z)}
        else:                    # coronal:  img_x→vox_x(sag), (Z-1)-img_y→vox_z(ax)
            updates = {0: _clamp(img_x, X), 2: _clamp((Z - 1) - img_y, Z)}

        for axis, idx in updates.items():
            self._axis_slices[axis] = idx
            self._multi_canvas.set_slice(axis, idx)
            self._render_single_axis(axis, idx)
        self._update_crosshair()
        self._update_info()

    def _on_cursor_move(self, img_x: int, img_y: int) -> None:
        """Update status bar with pixel coordinates and intensity (single-axis mode)."""
        raw = self._last_raw_per_axis.get(self._current_axis)
        if raw is None:
            return
        h, w = raw.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            val = raw[img_y, img_x]
            self._status_var.set(
                f"({img_x}, {img_y})  Value: {val:.1f}  |  "
                f"Dims: {w}x{h}  Zoom: {self._canvas.zoom_percent}%"
            )

    def _on_multi_cursor_move(self, axis: int, img_x: int, img_y: int) -> None:
        """Update status bar from multi-axis panel cursor movement."""
        raw = self._last_raw_per_axis.get(axis)
        if raw is None:
            return
        h, w = raw.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            val = raw[img_y, img_x]
            label = _AXIS_LABEL[axis]
            self._status_var.set(
                f"[{label}] ({img_x}, {img_y})  Value: {val:.1f}  |  Dims: {w}x{h}"
            )

    # ------------------------------------------------------------------
    # Crosshair overlay (NIfTI multi-axis)
    # ------------------------------------------------------------------

    def _update_crosshair(self) -> None:
        """Recalculate crosshair image coords from _axis_slices and redraw all panels."""
        if not self._is_multi_axis or self._multi_canvas is None:
            return
        if not isinstance(self._model, NiftiVolume):
            return
        Y = self._model.num_slices(1)
        Z = self._model.num_slices(2)
        vox_x = self._axis_slices[0]
        vox_y = self._axis_slices[1]
        vox_z = self._axis_slices[2]
        # Inverse of the click→voxel transforms in _on_crosshair_click:
        #   axial(2):   img=(vox_x, (Y-1)-vox_y)
        #   sagittal(0): img=(vox_y, (Z-1)-vox_z)
        #   coronal(1):  img=(vox_x, (Z-1)-vox_z)
        self._multi_canvas.set_crosshair_positions({
            2: (vox_x, (Y - 1) - vox_y),
            0: (vox_y, (Z - 1) - vox_z),
            1: (vox_x, (Z - 1) - vox_z),
        })
        self._multi_canvas.refresh_crosshair()

    def _on_open_recent(self, path: str, kind: str) -> None:
        if kind == "dir":
            self.open_directory(path)
        else:
            self.open_file(path)

    # ------------------------------------------------------------------
    # Progress bar (DICOM loading)
    # ------------------------------------------------------------------

    def _show_progress_bar(
        self, mode: Literal["determinate", "indeterminate"] = "determinate"
    ) -> None:
        self._progress_bar.config(value=0, maximum=100, mode=mode)
        self._progress_bar.pack(fill=tk.X, padx=4, pady=(0, 2), before=self._status_bar)
        if mode == "indeterminate":
            self._progress_bar.start(20)

    def _hide_progress_bar(self) -> None:
        self._progress_bar.stop()
        self._progress_bar.pack_forget()

    def _on_load_progress(self, done: int, total: int) -> None:
        pct = int(done / total * 100) if total else 0
        self._progress_bar.config(value=pct, maximum=100)
        self._status_var.set(status_scanning_dicom(done, total))

    # ------------------------------------------------------------------
    # Keyboard shortcuts overlay
    # ------------------------------------------------------------------

    def _show_shortcuts(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Keyboard Shortcuts")
        win.resizable(False, False)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Keyboard Shortcuts", font=("", 12, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 8), sticky=tk.W
        )

        for i, (key, desc) in enumerate(SHORTCUTS, start=1):
            ttk.Label(frame, text=key, font=("Courier", 10)).grid(
                row=i, column=0, sticky=tk.W, padx=(0, 16), pady=1
            )
            ttk.Label(frame, text=desc).grid(row=i, column=1, sticky=tk.W, pady=1)

        ttk.Button(frame, text="Close", command=win.destroy).grid(
            row=len(SHORTCUTS) + 2, column=0, columnspan=2, pady=(12, 0)
        )

    # ------------------------------------------------------------------

    def on_resize(self, _event=None) -> None:
        self._render_slice()

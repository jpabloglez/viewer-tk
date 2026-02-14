from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

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
from ..utils.theme import apply_font, apply_theme
from ..views.canvas import ImageCanvas
from ..views.info_bar import InfoBar
from ..views.menubar import MenuBar
from ..views.metadata import MetadataWindow
from ..views.multi_canvas import MultiAxisCanvas
from ..views.toolbar import Toolbar

logger = logging.getLogger(__name__)


class ViewerController:
    """Main controller — wires model, views, and user actions."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Medical Image Viewer")

        self._model: ImageVolume | None = None
        self._current_slice = 0
        self._current_axis = 2  # axial by default
        self._axis_slices: dict[int, int] = {0: 0, 1: 0, 2: 0}
        self._window_center: float | None = None
        self._window_width: float | None = None
        self._colormap = "gray"
        self._is_multi_axis = False
        self._loaded_path: str | None = None

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

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        self._status_bar = tk.Label(
            root, textvariable=self._status_var,
            bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=4,
        )
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # --- menu bar ---
        self._menubar = MenuBar(root)
        self._menubar.on_open_dir = self.open_directory
        self._menubar.on_open_file = self.open_file
        self._menubar.on_exit = root.destroy
        self._menubar.on_metadata = self._show_metadata
        self._menubar.on_reset_zoom = self._reset_zoom
        self._menubar.on_window_preset = self._on_window_preset
        self._menubar.on_theme_change = lambda name: apply_theme(root, name)
        self._menubar.on_font_size = lambda size: apply_font(root, size=size)
        self._menubar.on_font_weight = lambda wt: apply_font(root, weight=wt)

        # --- toolbar callbacks ---
        self._toolbar.on_open_dir = self.open_directory
        self._toolbar.on_open_file = self.open_file
        self._toolbar.on_metadata = self._show_metadata
        self._toolbar.on_window_preset = self._on_window_preset
        self._toolbar.on_colormap = self._on_colormap
        self._toolbar.on_window_manual = self._on_window_manual
        self._toolbar.on_zoom_fit = self._canvas.fit_view
        self._toolbar.on_zoom_actual = self._canvas.actual_size

        # --- cursor tracking ---
        self._canvas.on_cursor_move = self._on_cursor_move
        self._last_raw_slice = None  # cache for pixel value lookup

        # --- key bindings ---
        root.bind("<Left>", lambda e: self._step(-1))
        root.bind("<Right>", lambda e: self._step(1))
        root.bind("<Home>", lambda e: self._goto(0))
        root.bind("<End>", lambda e: self._goto_end())
        root.bind("<Control-o>", lambda e: self.open_directory())
        root.bind("<Control-O>", lambda e: self.open_file())
        root.bind("<Control-m>", lambda e: self._show_metadata())
        root.bind("<Control-0>", lambda e: self._reset_zoom())
        root.bind("<Control-q>", lambda e: root.destroy())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_directory(self, directory: str | None = None) -> None:
        if directory is None:
            directory = filedialog.askdirectory()
        if not directory:
            return
        self._toolbar.set_loading(True)
        self._status_var.set(f"Loading DICOM: {directory}...")
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
        self._status_var.set(f"Loading NIfTI: {file_path}...")
        threading.Thread(
            target=self._load_file_bg, args=(file_path,), daemon=True
        ).start()

    # ------------------------------------------------------------------
    # Background loading
    # ------------------------------------------------------------------

    def _load_directory_bg(self, directory: str) -> None:
        try:
            model = DicomVolume()
            model.load(directory)
            self.root.after(0, self._on_directory_loaded, model, directory)
        except Exception:
            logger.exception("Failed to load DICOM directory")
            msg = f"Failed to load directory:\n{directory}"
            self.root.after(
                0, lambda: messagebox.showerror("Error", msg)
            )
            self.root.after(0, lambda: self._toolbar.set_loading(False))
            self.root.after(0, lambda: self._status_var.set("Load failed"))

    def _on_directory_loaded(self, model: DicomVolume, path: str) -> None:
        self._model = model
        self._loaded_path = path
        self._current_slice = 0
        self._teardown_multi_axis()
        model.get_slice(0)
        center, width = model.get_window_defaults()
        self._window_center = center
        self._window_width = width
        self._update_slider()
        self._render_slice()
        self._update_info()
        self._toolbar.set_loading(False)
        self._status_var.set(f"DICOM: {path} — {model.num_slices()} slices")

    def _load_file_bg(self, file_path: str) -> None:
        try:
            model = NiftiVolume()
            model.load(file_path)
            self.root.after(0, self._on_file_loaded, model, file_path)
        except Exception:
            logger.exception("Failed to load NIfTI file")
            msg = f"Failed to load file:\n{file_path}"
            self.root.after(
                0, lambda: messagebox.showerror("Error", msg)
            )
            self.root.after(0, lambda: self._toolbar.set_loading(False))
            self.root.after(0, lambda: self._status_var.set("Load failed"))

    def _on_file_loaded(self, model: NiftiVolume, path: str) -> None:
        self._model = model
        self._loaded_path = path
        self._window_center = None
        self._window_width = None
        self._current_slice = 0
        self._axis_slices = {
            ax: model.num_slices(ax) // 2 for ax in (0, 1, 2)
        }
        self._setup_multi_axis()
        self._update_slider()
        self._render_slice()
        self._update_info()
        self._toolbar.set_loading(False)
        shape = [model.num_slices(ax) for ax in (0, 1, 2)]
        self._status_var.set(f"NIfTI: {path} — {shape[0]}x{shape[1]}x{shape[2]}")

    # ------------------------------------------------------------------
    # Multi-axis management
    # ------------------------------------------------------------------

    def _setup_multi_axis(self) -> None:
        """Switch to multi-axis view for NIfTI volumes."""
        if not isinstance(self._model, NiftiVolume):
            return
        self._canvas.pack_forget()
        self._slider.pack_forget()  # hide main slider in multi-axis mode

        if self._multi_canvas is None:
            self._multi_canvas = MultiAxisCanvas(self.root)
            self._multi_canvas.on_slice_change = self._on_multi_axis_slider
        self._multi_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4,
                                before=self._info_bar)
        self._is_multi_axis = True

        # Configure per-axis sliders
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

    def _on_multi_axis_slider(self, axis: int, index: int) -> None:
        """Called when any of the 3 per-axis sliders moves."""
        self._axis_slices[axis] = index
        self._render_single_axis(axis, index)
        self._update_info()

    # ------------------------------------------------------------------
    # Single-axis slider (DICOM mode)
    # ------------------------------------------------------------------

    def _update_slider(self) -> None:
        if self._model is None:
            return
        if self._is_multi_axis:
            return  # multi-axis sliders managed separately
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
            # Step axial axis by default in multi-axis mode
            axis = 2
            new = self._axis_slices[axis] + delta
            if 0 <= new < self._model.num_slices(axis):
                self._axis_slices[axis] = new
                self._multi_canvas.set_slice(axis, new)
                self._render_single_axis(axis, new)
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

        raw = self._model.get_slice(self._current_slice, self._current_axis)
        self._last_raw_slice = raw
        img = self._apply_pipeline(raw)
        self._canvas.display(img)
        self._toolbar.update_zoom_label(self._canvas.zoom_percent)

    def _render_all_axes(self) -> None:
        """Render all 3 axes using their independent slice indices."""
        for axis in (0, 1, 2):
            idx = self._axis_slices[axis]
            self._render_single_axis(axis, idx)

    def _render_single_axis(self, axis: int, index: int) -> None:
        """Render one axis panel in multi-axis view."""
        raw = self._model.get_slice(index, axis)
        img = self._apply_pipeline(raw)
        self._multi_canvas.display(axis, img, slice_idx=index)

    def _apply_pipeline(self, raw_data) -> Image.Image:
        """Normalize -> window/level -> colormap -> PIL Image."""
        if self._window_center is not None and self._window_width is not None:
            uint8 = apply_window_level(raw_data, self._window_center, self._window_width)
        else:
            uint8 = normalize_min_max(raw_data)
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
            messagebox.showinfo("Info", "Load an image first.")
            return
        meta = self._model.get_metadata()
        if meta is None:
            messagebox.showinfo("Info", "No metadata available.")
            return
        win = tk.Toplevel(self.root)
        MetadataWindow(win, meta)

    # ------------------------------------------------------------------
    # Toolbar callbacks
    # ------------------------------------------------------------------

    def _reset_zoom(self) -> None:
        """Reset zoom for whichever view mode is active."""
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
        self._render_slice()

    def _on_cursor_move(self, img_x: int, img_y: int) -> None:
        """Update status bar with pixel coordinates and intensity."""
        if self._last_raw_slice is None:
            return
        h, w = self._last_raw_slice.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            val = self._last_raw_slice[img_y, img_x]
            self._status_var.set(
                f"({img_x}, {img_y})  Value: {val:.1f}  |  "
                f"Dims: {w}x{h}  Zoom: {self._canvas.zoom_percent}%"
            )

    def on_resize(self, _event=None) -> None:
        self._render_slice()

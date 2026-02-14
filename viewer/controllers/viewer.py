import logging
import os
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
from ..views.canvas import ImageCanvas
from ..views.info_bar import InfoBar
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
        self._window_center: float | None = None
        self._window_width: float | None = None
        self._colormap = "gray"
        self._is_multi_axis = False

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

        # --- toolbar callbacks ---
        self._toolbar.on_open_dir = self.open_directory
        self._toolbar.on_open_file = self.open_file
        self._toolbar.on_metadata = self._show_metadata
        self._toolbar.on_window_preset = self._on_window_preset
        self._toolbar.on_colormap = self._on_colormap
        self._toolbar.on_zoom_fit = self._canvas.fit_view
        self._toolbar.on_zoom_actual = self._canvas.actual_size

        # --- key bindings ---
        root.bind("<Left>", lambda e: self._step(-1))
        root.bind("<Right>", lambda e: self._step(1))
        root.bind("<Home>", lambda e: self._goto(0))
        root.bind("<End>", lambda e: self._goto_end())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_directory(self, directory: str | None = None) -> None:
        if directory is None:
            directory = filedialog.askdirectory()
        if not directory:
            return
        self._toolbar.set_loading(True)
        thread = threading.Thread(
            target=self._load_directory_bg, args=(directory,), daemon=True
        )
        thread.start()

    def open_file(self, file_path: str | None = None) -> None:
        if file_path is None:
            file_path = filedialog.askopenfilename(
                filetypes=[("NIfTI files", "*.nii *.nii.gz"), ("All files", "*.*")]
            )
        if not file_path:
            return
        try:
            model = NiftiVolume()
            model.load(file_path)
            self._model = model
            self._window_center = None
            self._window_width = None
            self._current_slice = 0
            self._setup_multi_axis()
            self._update_slider()
            self._render_slice()
            self._update_info()
        except Exception as exc:
            logger.exception("Failed to load NIfTI file")
            messagebox.showerror("Error", f"Failed to load file:\n{exc}")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_directory_bg(self, directory: str) -> None:
        try:
            model = DicomVolume()
            model.load(directory)
            self.root.after(0, self._on_directory_loaded, model)
        except Exception as exc:
            logger.exception("Failed to load DICOM directory")
            self.root.after(
                0, lambda: messagebox.showerror("Error", f"Failed to load directory:\n{exc}")
            )
            self.root.after(0, lambda: self._toolbar.set_loading(False))

    def _on_directory_loaded(self, model: DicomVolume) -> None:
        self._model = model
        self._current_slice = 0
        self._teardown_multi_axis()
        # Try reading default window from first slice
        model.get_slice(0)
        center, width = model.get_window_defaults()
        self._window_center = center
        self._window_width = width
        self._update_slider()
        self._render_slice()
        self._update_info()
        self._toolbar.set_loading(False)

    def _setup_multi_axis(self) -> None:
        """Switch to multi-axis view for NIfTI volumes."""
        if not isinstance(self._model, NiftiVolume):
            return
        self._canvas.pack_forget()
        if self._multi_canvas is None:
            self._multi_canvas = MultiAxisCanvas(self.root)
        self._multi_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4,
                                before=self._info_bar)
        self._is_multi_axis = True

    def _teardown_multi_axis(self) -> None:
        if self._multi_canvas is not None:
            self._multi_canvas.pack_forget()
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4,
                          before=self._info_bar)
        self._is_multi_axis = False

    def _update_slider(self) -> None:
        if self._model is None:
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
            self._render_multi_axis()
            return

        raw = self._model.get_slice(self._current_slice, self._current_axis)
        img = self._apply_pipeline(raw)
        self._canvas.display(img)
        self._toolbar.update_zoom_label(self._canvas.zoom_percent)

    def _render_multi_axis(self) -> None:
        """Render all 3 axes for NIfTI multi-axis view."""
        for axis in (0, 1, 2):
            num = self._model.num_slices(axis)
            idx = self._current_slice if axis == self._current_axis else num // 2
            idx = min(idx, num - 1)
            raw = self._model.get_slice(idx, axis)
            img = self._apply_pipeline(raw)
            self._multi_canvas.display(axis, img)

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

    def _on_window_preset(self, name: str) -> None:
        if name == "Auto":
            self._window_center = None
            self._window_width = None
        else:
            self._window_center, self._window_width = WINDOW_PRESETS[name]
        self._render_slice()

    def _on_colormap(self, cmap: str) -> None:
        self._colormap = cmap
        self._render_slice()

    def on_resize(self, _event=None) -> None:
        self._render_slice()

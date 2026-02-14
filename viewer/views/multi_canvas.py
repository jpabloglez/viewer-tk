from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from ..utils.image import resize_to_fit

logger = logging.getLogger(__name__)

AXIS_LABELS = {0: "Sagittal", 1: "Coronal", 2: "Axial"}
AXIS_ORDER = [2, 0, 1]  # display order: axial, sagittal, coronal


class MultiAxisCanvas(ttk.Frame):
    """Three-panel canvas for axial, sagittal, and coronal views with
    independent sliders, slice labels, zoom and pan per axis."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvases: dict[int, tk.Canvas] = {}
        self._photos: dict[int, ImageTk.PhotoImage] = {}
        self._sliders: dict[int, tk.Scale] = {}
        self._slice_labels: dict[int, ttk.Label] = {}
        self._num_slices: dict[int, int] = {0: 1, 1: 1, 2: 1}
        self._source_images: dict[int, Image.Image] = {}

        # Per-axis zoom and pan state
        self._zoom: dict[int, float] = {0: 1.0, 1: 1.0, 2: 1.0}
        self._offset_x: dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.0}
        self._offset_y: dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.0}
        self._drag_start: dict[int, tuple[int, int] | None] = {0: None, 1: None, 2: None}

        # Callback: (axis: int, index: int) -> None, set by controller
        self.on_slice_change = None

        for col, axis in enumerate(AXIS_ORDER):
            frame = ttk.LabelFrame(self, text=AXIS_LABELS[axis])
            frame.grid(row=0, column=col, sticky="nsew", padx=2, pady=2)
            self.columnconfigure(col, weight=1)
            self.rowconfigure(0, weight=1)

            canvas = tk.Canvas(frame, bg="black", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            self._canvases[axis] = canvas

            # Zoom: mouse scroll
            canvas.bind("<MouseWheel>", lambda e, a=axis: self._on_mousewheel(a, e))
            canvas.bind("<Button-4>", lambda e, a=axis: self._on_mousewheel(a, e))
            canvas.bind("<Button-5>", lambda e, a=axis: self._on_mousewheel(a, e))

            # Pan: middle-click drag
            canvas.bind("<ButtonPress-2>", lambda e, a=axis: self._on_pan_start(a, e))
            canvas.bind("<B2-Motion>", lambda e, a=axis: self._on_pan_move(a, e))

            # Slice label overlay
            lbl = ttk.Label(frame, text="0 / 0")
            lbl.pack(side=tk.LEFT, padx=4)
            self._slice_labels[axis] = lbl

            # Per-axis slider
            slider = tk.Scale(
                frame, from_=0, to=0, orient=tk.HORIZONTAL,
                command=lambda val, a=axis: self._on_slider(a, val),
            )
            slider.pack(fill=tk.X, padx=2, pady=(0, 2))
            self._sliders[axis] = slider

    def configure_axis(self, axis: int, num_slices: int, initial: int = 0) -> None:
        """Set up slider range and initial value for an axis."""
        self._num_slices[axis] = num_slices
        slider = self._sliders[axis]
        slider.config(from_=0, to=max(0, num_slices - 1))
        slider.set(initial)
        self._update_label(axis, initial)

    def set_slice(self, axis: int, index: int) -> None:
        """Programmatically set a slider (e.g. from keyboard navigation)."""
        self._sliders[axis].set(index)
        self._update_label(axis, index)

    def display(self, axis: int, pil_image: Image.Image, slice_idx: int | None = None) -> None:
        self._source_images[axis] = pil_image
        self._render_axis(axis)
        if slice_idx is not None:
            self._update_label(axis, slice_idx)

    def _render_axis(self, axis: int) -> None:
        """Render a single axis panel with current zoom/pan."""
        if axis not in self._source_images:
            return
        canvas = self._canvases[axis]
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        src = self._source_images[axis]
        zoom = self._zoom[axis]

        if zoom == 1.0:
            img = resize_to_fit(src, cw, ch)
        else:
            new_w = max(1, int(src.width * zoom))
            new_h = max(1, int(src.height * zoom))
            img = src.resize((new_w, new_h), Image.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self._photos[axis] = photo
        canvas.delete("all")
        x = cw // 2 + int(self._offset_x[axis])
        y = ch // 2 + int(self._offset_y[axis])
        canvas.create_image(x, y, anchor=tk.CENTER, image=photo)

    def _update_label(self, axis: int, index: int) -> None:
        total = self._num_slices[axis]
        self._slice_labels[axis].config(text=f"{index + 1} / {total}")

    def _on_slider(self, axis: int, value: str) -> None:
        idx = int(float(value))
        self._update_label(axis, idx)
        if self.on_slice_change:
            self.on_slice_change(axis, idx)

    # --- zoom ---
    def _on_mousewheel(self, axis: int, event) -> None:
        if event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            factor = 0.9
        else:
            factor = 1.1
        self._zoom[axis] = max(0.1, min(self._zoom[axis] * factor, 20.0))
        self._render_axis(axis)

    # --- pan ---
    def _on_pan_start(self, axis: int, event) -> None:
        self._drag_start[axis] = (event.x, event.y)

    def _on_pan_move(self, axis: int, event) -> None:
        start = self._drag_start[axis]
        if start is None:
            return
        self._offset_x[axis] += event.x - start[0]
        self._offset_y[axis] += event.y - start[1]
        self._drag_start[axis] = (event.x, event.y)
        self._render_axis(axis)

    def reset_view(self) -> None:
        """Reset zoom and pan for all axes."""
        for axis in AXIS_ORDER:
            self._zoom[axis] = 1.0
            self._offset_x[axis] = 0.0
            self._offset_y[axis] = 0.0
            self._render_axis(axis)

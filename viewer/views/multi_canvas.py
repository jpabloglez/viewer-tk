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
    independent sliders and slice labels per axis."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvases: dict[int, tk.Canvas] = {}
        self._photos: dict[int, ImageTk.PhotoImage] = {}
        self._sliders: dict[int, tk.Scale] = {}
        self._slice_labels: dict[int, ttk.Label] = {}
        self._num_slices: dict[int, int] = {0: 1, 1: 1, 2: 1}

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
        canvas = self._canvases[axis]
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        img = resize_to_fit(pil_image, cw, ch)
        photo = ImageTk.PhotoImage(img)
        self._photos[axis] = photo
        canvas.delete("all")
        canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=photo)
        if slice_idx is not None:
            self._update_label(axis, slice_idx)

    def _update_label(self, axis: int, index: int) -> None:
        total = self._num_slices[axis]
        self._slice_labels[axis].config(text=f"{index + 1} / {total}")

    def _on_slider(self, axis: int, value: str) -> None:
        idx = int(float(value))
        self._update_label(axis, idx)
        if self.on_slice_change:
            self.on_slice_change(axis, idx)

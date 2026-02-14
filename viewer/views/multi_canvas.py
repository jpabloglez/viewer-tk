import logging
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from ..utils.image import resize_to_fit

logger = logging.getLogger(__name__)

AXIS_LABELS = {0: "Sagittal", 1: "Coronal", 2: "Axial"}


class MultiAxisCanvas(ttk.Frame):
    """Three-panel canvas for axial, sagittal, and coronal views."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvases: dict[int, tk.Canvas] = {}
        self._photos: dict[int, ImageTk.PhotoImage] = {}
        self._slices: dict[int, int] = {0: 0, 1: 0, 2: 0}

        # Callback when a crosshair click changes a slice index
        self.on_slice_change = None  # (axis, index) -> None

        for i, axis in enumerate([2, 0, 1]):  # axial, sagittal, coronal
            frame = ttk.LabelFrame(self, text=AXIS_LABELS[axis])
            frame.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
            self.columnconfigure(i, weight=1)
            self.rowconfigure(0, weight=1)

            canvas = tk.Canvas(frame, bg="black", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            self._canvases[axis] = canvas

    def display(self, axis: int, pil_image: Image.Image) -> None:
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

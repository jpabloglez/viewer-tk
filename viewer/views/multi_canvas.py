from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

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

        # Callbacks set by controller
        self.on_slice_change: Callable[[int, int], None] | None = None
        # Callbacks: (axis, img_x, img_y) -> None
        self.on_cursor_move: Callable[[int, int, int], None] | None = None
        self.on_crosshair_click: Callable[[int, int, int], None] | None = None

        # Crosshair overlay: source-image coords per axis (None = not set yet)
        self._crosshair_pos: dict[int, tuple[int, int] | None] = {0: None, 1: None, 2: None}

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

            # Crosshair click
            canvas.bind("<Button-1>", lambda e, a=axis: self._on_click(a, e))

            # Cursor tracking
            canvas.bind("<Motion>", lambda e, a=axis: self._on_motion(a, e))

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

    def set_crosshair_positions(self, positions: dict[int, tuple[int, int]]) -> None:
        """Update crosshair overlay positions (source-image coords). Does not redraw."""
        self._crosshair_pos.update(positions)

    def refresh_crosshair(self) -> None:
        """Redraw all panels that already have a source image (no new pixel data needed)."""
        for axis in AXIS_ORDER:
            if axis in self._source_images:
                self._render_axis(axis)

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
            img = src.resize((new_w, new_h), Image.Resampling.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self._photos[axis] = photo
        canvas.delete("all")
        x = cw // 2 + int(self._offset_x[axis])
        y = ch // 2 + int(self._offset_y[axis])
        canvas.create_image(x, y, anchor=tk.CENTER, image=photo)

        # Crosshair overlay
        ch_pos = self._crosshair_pos.get(axis)
        if ch_pos is not None:
            lx, ly = self._image_to_canvas(axis, ch_pos[0], ch_pos[1])
            canvas.create_line(lx, 0, lx, ch, fill="#00ffff", width=1)
            canvas.create_line(0, ly, cw, ly, fill="#00ffff", width=1)

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

    # --- crosshair click ---
    def _on_click(self, axis: int, event) -> None:
        if self.on_crosshair_click is None:
            return
        coords = self._canvas_to_image(axis, event.x, event.y)
        if coords:
            self.on_crosshair_click(axis, *coords)

    # --- cursor tracking ---
    def _on_motion(self, axis: int, event) -> None:
        if self.on_cursor_move is None:
            return
        coords = self._canvas_to_image(axis, event.x, event.y)
        if coords:
            self.on_cursor_move(axis, *coords)

    def _image_to_canvas(self, axis: int, img_x: int, img_y: int) -> tuple[int, int]:
        """Convert source-image pixel coords to canvas pixel coords."""
        canvas = self._canvases[axis]
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        src = self._source_images[axis]
        photo = self._photos[axis]
        dw = photo.width()
        dh = photo.height()
        img_cx = cw // 2 + int(self._offset_x[axis])
        img_cy = ch // 2 + int(self._offset_y[axis])
        tl_x = img_cx - dw // 2
        tl_y = img_cy - dh // 2
        lx = tl_x + int(img_x * dw / max(src.width, 1))
        ly = tl_y + int(img_y * dh / max(src.height, 1))
        return lx, ly

    def _canvas_to_image(self, axis: int, cx: int, cy: int) -> tuple[int, int] | None:
        """Convert canvas pixel coords to source image pixel coords."""
        if axis not in self._source_images or axis not in self._photos:
            return None
        canvas = self._canvases[axis]
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        src = self._source_images[axis]
        photo = self._photos[axis]
        dw = photo.width()
        dh = photo.height()
        img_cx = cw // 2 + int(self._offset_x[axis])
        img_cy = ch // 2 + int(self._offset_y[axis])
        rx = cx - (img_cx - dw // 2)
        ry = cy - (img_cy - dh // 2)
        if rx < 0 or ry < 0 or rx >= dw or ry >= dh:
            return None
        src_x = min(int(rx * src.width / dw), src.width - 1)
        src_y = min(int(ry * src.height / dh), src.height - 1)
        return src_x, src_y

    def reset_view(self) -> None:
        """Reset zoom and pan for all axes."""
        for axis in AXIS_ORDER:
            self._zoom[axis] = 1.0
            self._offset_x[axis] = 0.0
            self._offset_y[axis] = 0.0
            self._render_axis(axis)

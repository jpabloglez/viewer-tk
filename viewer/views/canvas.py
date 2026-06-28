from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from PIL import Image, ImageTk

from ..utils.image import resize_to_fit

logger = logging.getLogger(__name__)

_HINT_TEXT = "Open a DICOM folder  (Ctrl+O)\nor a NIfTI file  (Ctrl+Shift+O)"


class ImageCanvas(ttk.Frame):
    """Canvas that displays a PIL image centered, with zoom, pan,
    cursor tracking, right-click W/L drag, and optional measure overlay."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._photo: ImageTk.PhotoImage | None = None
        self._zoom = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._drag_start: tuple[int, int] | None = None
        self._source_image: Image.Image | None = None

        # Zoom: mouse wheel
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)

        # Pan: middle-click drag
        self._canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self._canvas.bind("<B2-Motion>", self._on_pan_move)

        # Right-click drag: W/L adjust (horizontal → width, vertical → center)
        self._canvas.bind("<ButtonPress-3>", self._on_wl_start)
        self._canvas.bind("<B3-Motion>", self._on_wl_drag_move)
        self._wl_drag_start: tuple[int, int] | None = None
        self.on_wl_drag: Callable[[float, float], None] | None = None

        # Left click: measurement points
        self._canvas.bind("<Button-1>", self._on_left_click)
        self._measure_active = False
        self._measure_pts: list[tuple[int, int]] = []  # stored in image coords
        self.on_measure_update: Callable[[list[tuple[int, int]]], None] | None = None

        # Cursor tracking
        self._canvas.bind("<Motion>", self._on_motion)
        self.on_cursor_move: Callable[[int, int], None] | None = None

        # Empty-state hint
        self._canvas.bind("<Configure>", self._on_configure)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def display(self, pil_image: Image.Image) -> None:
        self._source_image = pil_image
        self._render()

    def set_measure_mode(self, active: bool) -> None:
        self._measure_active = active
        if not active:
            self._measure_pts = []
            self._render()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._render()

    def fit_view(self) -> None:
        self.reset_view()

    def actual_size(self) -> None:
        if self._source_image is None:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        fit = resize_to_fit(self._source_image, cw, ch)
        self._zoom = self._source_image.width / max(fit.width, 1)
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._render()

    @property
    def zoom_percent(self) -> int:
        return int(self._zoom * 100)

    def get_display_size(self) -> tuple[int, int]:
        return self._canvas.winfo_width(), self._canvas.winfo_height()

    # ------------------------------------------------------------------
    # Internal render
    # ------------------------------------------------------------------

    def _on_configure(self, _event=None) -> None:
        if self._source_image is None:
            self._draw_empty_state()

    def _draw_empty_state(self) -> None:
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self._canvas.delete("all")
        self._canvas.create_text(
            cw // 2, ch // 2,
            text=_HINT_TEXT,
            fill="#4a4a4a",
            font=("", 13),
            justify="center",
        )

    def _render(self) -> None:
        if self._source_image is None:
            self._draw_empty_state()
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        if self._zoom == 1.0:
            img = resize_to_fit(self._source_image, cw, ch)
        else:
            new_w = max(1, int(self._source_image.width * self._zoom))
            new_h = max(1, int(self._source_image.height * self._zoom))
            img = self._source_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        x = cw // 2 + int(self._offset_x)
        y = ch // 2 + int(self._offset_y)
        self._canvas.create_image(x, y, anchor=tk.CENTER, image=self._photo)
        self._draw_measure_overlay()

    # ------------------------------------------------------------------
    # Measure overlay
    # ------------------------------------------------------------------

    def _draw_measure_overlay(self) -> None:
        if not self._measure_pts:
            return
        pts_canvas = [self._image_to_canvas(ix, iy) for ix, iy in self._measure_pts]
        pts_canvas = [p for p in pts_canvas if p is not None]

        for i, (cx, cy) in enumerate(pts_canvas, 1):
            r = 4
            self._canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                      outline="#ffff00", width=2)
            self._canvas.create_text(cx + 9, cy - 9, text=str(i),
                                      fill="#ffff00", font=("", 9, "bold"))

        if len(pts_canvas) == 2:
            (x1, y1), (x2, y2) = pts_canvas
            self._canvas.create_line(x1, y1, x2, y2, fill="#ffff00", width=2)

    def _image_to_canvas(self, ix: int, iy: int) -> tuple[int, int] | None:
        if self._source_image is None or self._photo is None:
            return None
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        dw = self._photo.width()
        dh = self._photo.height()
        img_cx = cw // 2 + int(self._offset_x)
        img_cy = ch // 2 + int(self._offset_y)
        tl_x = img_cx - dw // 2
        tl_y = img_cy - dh // 2
        cx = tl_x + int(ix * dw / self._source_image.width)
        cy = tl_y + int(iy * dh / self._source_image.height)
        return cx, cy

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _on_mousewheel(self, event) -> None:
        if event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            factor = 0.9
        else:
            factor = 1.1
        self._zoom = max(0.1, min(self._zoom * factor, 20.0))
        self._render()

    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------

    def _on_pan_start(self, event) -> None:
        self._drag_start = (event.x, event.y)

    def _on_pan_move(self, event) -> None:
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._offset_x += dx
        self._offset_y += dy
        self._drag_start = (event.x, event.y)
        self._render()

    # ------------------------------------------------------------------
    # W/L drag (right click)
    # ------------------------------------------------------------------

    def _on_wl_start(self, event) -> None:
        self._wl_drag_start = (event.x, event.y)

    def _on_wl_drag_move(self, event) -> None:
        if self._wl_drag_start is None or self.on_wl_drag is None:
            return
        dx = event.x - self._wl_drag_start[0]
        dy = event.y - self._wl_drag_start[1]
        self._wl_drag_start = (event.x, event.y)
        self.on_wl_drag(-dy * 2.0, dx * 4.0)

    # ------------------------------------------------------------------
    # Measurement clicks (left click)
    # ------------------------------------------------------------------

    def _on_left_click(self, event) -> None:
        if not self._measure_active:
            return
        coords = self._canvas_to_image(event.x, event.y)
        if coords is None:
            return
        if len(self._measure_pts) >= 2:
            self._measure_pts = [coords]
        else:
            self._measure_pts.append(coords)
        self._render()
        if self.on_measure_update:
            self.on_measure_update(list(self._measure_pts))

    # ------------------------------------------------------------------
    # Cursor tracking
    # ------------------------------------------------------------------

    def _on_motion(self, event) -> None:
        if self.on_cursor_move is None or self._source_image is None:
            return
        coords = self._canvas_to_image(event.x, event.y)
        if coords:
            self.on_cursor_move(*coords)

    def _canvas_to_image(self, cx: int, cy: int) -> tuple[int, int] | None:
        """Convert canvas pixel to source image pixel. Returns None if outside."""
        if self._source_image is None or self._photo is None:
            return None
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        img_cx = cw // 2 + int(self._offset_x)
        img_cy = ch // 2 + int(self._offset_y)
        dw = self._photo.width()
        dh = self._photo.height()
        rx = cx - (img_cx - dw // 2)
        ry = cy - (img_cy - dh // 2)
        if rx < 0 or ry < 0 or rx >= dw or ry >= dh:
            return None
        src_x = min(int(rx * self._source_image.width / dw), self._source_image.width - 1)
        src_y = min(int(ry * self._source_image.height / dh), self._source_image.height - 1)
        return src_x, src_y

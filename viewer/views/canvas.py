import logging
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from ..utils.image import resize_to_fit

logger = logging.getLogger(__name__)


class ImageCanvas(ttk.Frame):
    """Canvas that displays a PIL image centered, with zoom and pan support."""

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
        self._canvas.bind("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self._canvas.bind("<Button-5>", self._on_mousewheel)  # Linux scroll down

        # Pan: middle-click drag
        self._canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self._canvas.bind("<B2-Motion>", self._on_pan_move)

    def display(self, pil_image: Image.Image) -> None:
        """Display *pil_image* on the canvas with current zoom/pan."""
        self._source_image = pil_image
        self._render()

    def _render(self) -> None:
        if self._source_image is None:
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
            img = self._source_image.resize((new_w, new_h), Image.LANCZOS)

        self._photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        x = cw // 2 + int(self._offset_x)
        y = ch // 2 + int(self._offset_y)
        self._canvas.create_image(x, y, anchor=tk.CENTER, image=self._photo)

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

    # --- zoom ---
    def _on_mousewheel(self, event):
        if event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            factor = 0.9
        else:
            factor = 1.1
        self._zoom = max(0.1, min(self._zoom * factor, 20.0))
        self._render()

    # --- pan ---
    def _on_pan_start(self, event):
        self._drag_start = (event.x, event.y)

    def _on_pan_move(self, event):
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._offset_x += dx
        self._offset_y += dy
        self._drag_start = (event.x, event.y)
        self._render()

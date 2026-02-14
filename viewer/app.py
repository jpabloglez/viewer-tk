from __future__ import annotations

import logging
import tkinter as tk

from .controllers.viewer import ViewerController
from .utils.theme import apply_theme

logger = logging.getLogger(__name__)


def run(directory: str | None = None, image: str | None = None) -> None:
    """Create the Tk root and launch the viewer."""
    root = tk.Tk()
    root.geometry("900x700")

    apply_theme(root, "dark")

    controller = ViewerController(root)

    # Debounced resize — avoid re-rendering on every pixel change
    _resize_id = None

    def _on_configure(event):
        nonlocal _resize_id
        if event.widget is root:
            if _resize_id is not None:
                root.after_cancel(_resize_id)
            _resize_id = root.after(150, controller.on_resize)

    root.bind("<Configure>", _on_configure)

    # Graceful shutdown
    def _on_close():
        logger.info("Shutting down")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    # Auto-load if paths given via CLI
    if directory:
        root.after(100, controller.open_directory, directory)
    elif image:
        root.after(100, controller.open_file, image)

    logger.info("Starting mainloop")
    root.mainloop()

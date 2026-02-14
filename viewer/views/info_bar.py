import tkinter as tk
from tkinter import ttk


class InfoBar(ttk.Frame):
    """Data-driven info bar that shows key-value pairs from a dict."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._labels: dict[str, ttk.Label] = {}
        style = ttk.Style()
        style.configure("Info.TLabel", background="#e6f3ff")
        self.configure(style="Info.TFrame")
        style.configure("Info.TFrame", background="#e6f3ff")

    def update_info(self, info: dict[str, str]) -> None:
        """Create/update labels from *info* dict. Removes stale labels."""
        # Remove labels not in new info
        for key in list(self._labels.keys()):
            if key not in info:
                self._labels[key].destroy()
                del self._labels[key]

        col = 0
        for key, value in info.items():
            text = f"{key}: {value}"
            if key in self._labels:
                self._labels[key].config(text=text)
            else:
                lbl = ttk.Label(self, text=text, style="Info.TLabel")
                lbl.grid(row=col // 3, column=col % 3, sticky="w", padx=5, pady=2)
                self._labels[key] = lbl
            col += 1

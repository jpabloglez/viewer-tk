import logging
import tkinter as tk
from tkinter import ttk

from ..utils.normalization import WINDOW_PRESETS

logger = logging.getLogger(__name__)

COLORMAPS = ["gray", "hot", "jet", "bone"]


class Toolbar(ttk.Frame):
    """Top toolbar with buttons, window presets, colormap, and zoom controls."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # Callbacks — set by the controller
        self.on_open_dir = None
        self.on_open_file = None
        self.on_metadata = None
        self.on_window_preset = None
        self.on_colormap = None
        self.on_zoom_fit = None
        self.on_zoom_actual = None

        # --- buttons ---
        self._btn_open_dir = ttk.Button(self, text="Open Dir", command=self._open_dir)
        self._btn_open_dir.pack(side=tk.LEFT, padx=2)

        self._btn_open_file = ttk.Button(self, text="Open File", command=self._open_file)
        self._btn_open_file.pack(side=tk.LEFT, padx=2)

        self._btn_metadata = ttk.Button(self, text="Metadata", command=self._metadata)
        self._btn_metadata.pack(side=tk.LEFT, padx=2)

        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # --- window preset ---
        ttk.Label(self, text="Window:").pack(side=tk.LEFT, padx=(4, 0))
        self._window_var = tk.StringVar(value="Auto")
        presets = ["Auto"] + list(WINDOW_PRESETS.keys())
        self._window_combo = ttk.Combobox(
            self, textvariable=self._window_var,
            values=presets, state="readonly", width=12,
        )
        self._window_combo.pack(side=tk.LEFT, padx=2)
        self._window_combo.bind("<<ComboboxSelected>>", self._on_window_change)

        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # --- colormap ---
        ttk.Label(self, text="Colormap:").pack(side=tk.LEFT, padx=(4, 0))
        self._cmap_var = tk.StringVar(value="gray")
        self._cmap_combo = ttk.Combobox(
            self, textvariable=self._cmap_var,
            values=COLORMAPS, state="readonly", width=8,
        )
        self._cmap_combo.pack(side=tk.LEFT, padx=2)
        self._cmap_combo.bind("<<ComboboxSelected>>", self._on_cmap_change)

        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # --- zoom ---
        self._btn_fit = ttk.Button(self, text="Fit", command=self._zoom_fit)
        self._btn_fit.pack(side=tk.LEFT, padx=2)
        self._btn_actual = ttk.Button(self, text="1:1", command=self._zoom_actual)
        self._btn_actual.pack(side=tk.LEFT, padx=2)
        self._zoom_label = ttk.Label(self, text="100%")
        self._zoom_label.pack(side=tk.LEFT, padx=4)

    def update_zoom_label(self, percent: int) -> None:
        self._zoom_label.config(text=f"{percent}%")

    def set_loading(self, loading: bool) -> None:
        state = "disabled" if loading else "!disabled"
        for w in (self._btn_open_dir, self._btn_open_file, self._btn_metadata):
            w.state([state])

    # --- internal callbacks ---
    def _open_dir(self):
        if self.on_open_dir:
            self.on_open_dir()

    def _open_file(self):
        if self.on_open_file:
            self.on_open_file()

    def _metadata(self):
        if self.on_metadata:
            self.on_metadata()

    def _on_window_change(self, _event=None):
        if self.on_window_preset:
            self.on_window_preset(self._window_var.get())

    def _on_cmap_change(self, _event=None):
        if self.on_colormap:
            self.on_colormap(self._cmap_var.get())

    def _zoom_fit(self):
        if self.on_zoom_fit:
            self.on_zoom_fit()

    def _zoom_actual(self):
        if self.on_zoom_actual:
            self.on_zoom_actual()

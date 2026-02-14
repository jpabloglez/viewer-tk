from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from ..utils.normalization import WINDOW_PRESETS

logger = logging.getLogger(__name__)

COLORMAPS = ["gray", "hot", "jet", "bone"]


class Toolbar(ttk.Frame):
    """Top toolbar with buttons, window presets, manual W/L sliders,
    colormap, and zoom controls."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # Callbacks — set by the controller
        self.on_open_dir = None
        self.on_open_file = None
        self.on_metadata = None
        self.on_window_preset = None
        self.on_window_manual = None
        self.on_colormap = None
        self.on_zoom_fit = None
        self.on_zoom_actual = None

        # --- Row 0: buttons + presets + colormap + zoom ---
        row0 = ttk.Frame(self)
        row0.pack(fill=tk.X)

        self._btn_open_dir = ttk.Button(row0, text="Open Dir", command=self._open_dir)
        self._btn_open_dir.pack(side=tk.LEFT, padx=2)

        self._btn_open_file = ttk.Button(row0, text="Open File", command=self._open_file)
        self._btn_open_file.pack(side=tk.LEFT, padx=2)

        self._btn_metadata = ttk.Button(row0, text="Metadata", command=self._metadata)
        self._btn_metadata.pack(side=tk.LEFT, padx=2)

        ttk.Separator(row0, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Window preset
        ttk.Label(row0, text="Window:").pack(side=tk.LEFT, padx=(4, 0))
        self._window_var = tk.StringVar(value="Auto")
        presets = ["Auto"] + list(WINDOW_PRESETS.keys())
        self._window_combo = ttk.Combobox(
            row0, textvariable=self._window_var,
            values=presets, state="readonly", width=12,
        )
        self._window_combo.pack(side=tk.LEFT, padx=2)
        self._window_combo.bind("<<ComboboxSelected>>", self._on_window_change)

        ttk.Separator(row0, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Colormap
        ttk.Label(row0, text="Colormap:").pack(side=tk.LEFT, padx=(4, 0))
        self._cmap_var = tk.StringVar(value="gray")
        self._cmap_combo = ttk.Combobox(
            row0, textvariable=self._cmap_var,
            values=COLORMAPS, state="readonly", width=8,
        )
        self._cmap_combo.pack(side=tk.LEFT, padx=2)
        self._cmap_combo.bind("<<ComboboxSelected>>", self._on_cmap_change)

        ttk.Separator(row0, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Zoom
        self._btn_fit = ttk.Button(row0, text="Fit", command=self._zoom_fit)
        self._btn_fit.pack(side=tk.LEFT, padx=2)
        self._btn_actual = ttk.Button(row0, text="1:1", command=self._zoom_actual)
        self._btn_actual.pack(side=tk.LEFT, padx=2)
        self._zoom_label = ttk.Label(row0, text="100%")
        self._zoom_label.pack(side=tk.LEFT, padx=4)

        # --- Row 1: manual window/level sliders ---
        row1 = ttk.Frame(self)
        row1.pack(fill=tk.X, pady=(2, 0))

        self._suppress_wl_callback = False

        ttk.Label(row1, text="Center:").pack(side=tk.LEFT, padx=(4, 0))
        self._center_var = tk.DoubleVar(value=0)
        self._center_slider = tk.Scale(
            row1, from_=-1024, to=3072, orient=tk.HORIZONTAL,
            variable=self._center_var, command=self._on_manual_wl,
            showvalue=True, length=150,
        )
        self._center_slider.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text="Width:").pack(side=tk.LEFT, padx=(8, 0))
        self._width_var = tk.DoubleVar(value=1)
        self._width_slider = tk.Scale(
            row1, from_=1, to=4096, orient=tk.HORIZONTAL,
            variable=self._width_var, command=self._on_manual_wl,
            showvalue=True, length=150,
        )
        self._width_slider.pack(side=tk.LEFT, padx=2)

    def update_zoom_label(self, percent: int) -> None:
        self._zoom_label.config(text=f"{percent}%")

    def set_loading(self, loading: bool) -> None:
        state = "disabled" if loading else "!disabled"
        for w in (self._btn_open_dir, self._btn_open_file, self._btn_metadata):
            w.state([state])

    def sync_window_sliders(self, center: float | None, width: float | None) -> None:
        """Update manual sliders to match a preset or auto selection.
        Suppresses callback to avoid re-render loop."""
        self._suppress_wl_callback = True
        if center is not None and width is not None:
            self._center_slider.set(center)
            self._width_slider.set(max(1, width))
        else:
            self._center_slider.set(0)
            self._width_slider.set(1)
        self._suppress_wl_callback = False

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

    def _on_manual_wl(self, _value=None):
        if self._suppress_wl_callback:
            return
        center = self._center_var.get()
        width = self._width_var.get()
        # Switch combo to show we're no longer on a preset
        self._window_var.set("Auto")
        if self.on_window_manual:
            self.on_window_manual(center, width)

    def _on_cmap_change(self, _event=None):
        if self.on_colormap:
            self.on_colormap(self._cmap_var.get())

    def _zoom_fit(self):
        if self.on_zoom_fit:
            self.on_zoom_fit()

    def _zoom_actual(self):
        if self.on_zoom_actual:
            self.on_zoom_actual()

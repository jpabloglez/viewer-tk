from __future__ import annotations

import tkinter as tk

from ..utils.normalization import WINDOW_PRESETS
from ..utils.theme import get_current_font_size, get_current_font_weight, get_current_theme

FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20]


class MenuBar(tk.Menu):
    """Application menu bar: File, View, Tools."""

    def __init__(self, root: tk.Tk, **kwargs):
        super().__init__(root, **kwargs)
        root.config(menu=self)

        # Callbacks — set by the controller
        self.on_open_dir = None
        self.on_open_file = None
        self.on_exit = None
        self.on_metadata = None
        self.on_reset_zoom = None
        self.on_window_preset = None
        self.on_theme_change = None     # (name: str) -> None
        self.on_font_size = None        # (size: int) -> None
        self.on_font_weight = None      # (weight: str) -> None

        # --- File ---
        file_menu = tk.Menu(self, tearoff=0)
        file_menu.add_command(
            label="Open DICOM Directory...",
            accelerator="Ctrl+O",
            command=self._open_dir,
        )
        file_menu.add_command(
            label="Open NIfTI File...",
            accelerator="Ctrl+Shift+O",
            command=self._open_file,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit",
            accelerator="Ctrl+Q",
            command=self._exit,
        )
        self.add_cascade(label="File", menu=file_menu)

        # --- View ---
        view_menu = tk.Menu(self, tearoff=0)
        view_menu.add_command(
            label="Metadata",
            accelerator="Ctrl+M",
            command=self._metadata,
        )
        view_menu.add_command(
            label="Reset Zoom",
            accelerator="Ctrl+0",
            command=self._reset_zoom,
        )
        view_menu.add_separator()

        # Theme submenu
        theme_menu = tk.Menu(view_menu, tearoff=0)
        self._theme_var = tk.StringVar(value=get_current_theme())
        for name in ("dark", "light"):
            theme_menu.add_radiobutton(
                label=name.capitalize(),
                variable=self._theme_var,
                value=name,
                command=self._on_theme,
            )
        view_menu.add_cascade(label="Theme", menu=theme_menu)

        # Font size submenu
        font_size_menu = tk.Menu(view_menu, tearoff=0)
        self._font_size_var = tk.IntVar(value=get_current_font_size())
        for size in FONT_SIZES:
            font_size_menu.add_radiobutton(
                label=str(size),
                variable=self._font_size_var,
                value=size,
                command=self._on_font_size,
            )
        view_menu.add_cascade(label="Font Size", menu=font_size_menu)

        # Font weight submenu
        font_weight_menu = tk.Menu(view_menu, tearoff=0)
        self._font_weight_var = tk.StringVar(value=get_current_font_weight())
        for weight in ("normal", "bold"):
            font_weight_menu.add_radiobutton(
                label=weight.capitalize(),
                variable=self._font_weight_var,
                value=weight,
                command=self._on_font_weight,
            )
        view_menu.add_cascade(label="Font Weight", menu=font_weight_menu)

        self.add_cascade(label="View", menu=view_menu)

        # --- Tools ---
        tools_menu = tk.Menu(self, tearoff=0)
        presets_menu = tk.Menu(tools_menu, tearoff=0)
        presets_menu.add_command(
            label="Auto",
            command=lambda: self._preset("Auto"),
        )
        presets_menu.add_separator()
        for name in WINDOW_PRESETS:
            presets_menu.add_command(
                label=name,
                command=lambda n=name: self._preset(n),
            )
        tools_menu.add_cascade(label="Window Presets", menu=presets_menu)
        self.add_cascade(label="Tools", menu=tools_menu)

    # --- internal callbacks ---
    def _open_dir(self):
        if self.on_open_dir:
            self.on_open_dir()

    def _open_file(self):
        if self.on_open_file:
            self.on_open_file()

    def _exit(self):
        if self.on_exit:
            self.on_exit()

    def _metadata(self):
        if self.on_metadata:
            self.on_metadata()

    def _reset_zoom(self):
        if self.on_reset_zoom:
            self.on_reset_zoom()

    def _preset(self, name: str):
        if self.on_window_preset:
            self.on_window_preset(name)

    def _on_theme(self):
        if self.on_theme_change:
            self.on_theme_change(self._theme_var.get())

    def _on_font_size(self):
        if self.on_font_size:
            self.on_font_size(self._font_size_var.get())

    def _on_font_weight(self):
        if self.on_font_weight:
            self.on_font_weight(self._font_weight_var.get())

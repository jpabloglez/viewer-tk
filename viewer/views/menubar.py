from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..utils.normalization import WINDOW_PRESETS


class MenuBar(tk.Menu):
    """Application menu bar: File, View, Tools."""

    def __init__(self, root: tk.Tk, **kwargs):
        super().__init__(root, **kwargs)
        root.config(menu=self)

        # Callbacks — set by the controller
        self.on_open_dir: Callable | None = None
        self.on_open_file: Callable | None = None
        self.on_open_recent: Callable[[str, str], None] | None = None  # (path, kind)
        self.on_save_view: Callable | None = None
        self.on_exit: Callable | None = None
        self.on_metadata: Callable | None = None
        self.on_reset_zoom: Callable | None = None
        self.on_window_preset: Callable[[str], None] | None = None
        self.on_histogram: Callable | None = None
        self.on_show_shortcuts: Callable | None = None

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

        # Open Recent submenu (populated dynamically via refresh_recent)
        self._recent_menu = tk.Menu(file_menu, tearoff=0)
        self._recent_menu.add_command(label="(empty)", state="disabled")
        file_menu.add_cascade(label="Open Recent", menu=self._recent_menu)

        file_menu.add_separator()
        file_menu.add_command(
            label="Save View...",
            accelerator="Ctrl+S",
            command=self._save_view,
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
        self.add_cascade(label="View", menu=view_menu)

        # --- Tools ---
        tools_menu = tk.Menu(self, tearoff=0)
        presets_menu = tk.Menu(tools_menu, tearoff=0)
        presets_menu.add_command(label="Auto", command=lambda: self._preset("Auto"))
        presets_menu.add_separator()
        for name in WINDOW_PRESETS:
            presets_menu.add_command(
                label=name,
                command=lambda n=name: self._preset(n),  # type: ignore[misc]
            )
        tools_menu.add_cascade(label="Window Presets", menu=presets_menu)
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Histogram",
            accelerator="Ctrl+H",
            command=self._histogram,
        )
        self.add_cascade(label="Tools", menu=tools_menu)

        # --- Help ---
        help_menu = tk.Menu(self, tearoff=0)
        help_menu.add_command(
            label="Keyboard Shortcuts",
            accelerator="?",
            command=self._show_shortcuts,
        )
        self.add_cascade(label="Help", menu=help_menu)

    def refresh_recent(self, items: list[dict]) -> None:
        """Repopulate the Open Recent submenu from a list of recent entries."""
        self._recent_menu.delete(0, "end")
        if not items:
            self._recent_menu.add_command(label="(empty)", state="disabled")
            return
        for item in items:
            path = item.get("path", "")
            kind = item.get("kind", "file")
            name = item.get("name", path)
            tag = "dir" if kind == "dir" else "nii"
            self._recent_menu.add_command(
                label=f"{name}  [{tag}]",
                command=lambda p=path, k=kind: self._open_recent(p, k),  # type: ignore[misc]
            )

    # --- internal callbacks ---
    def _open_dir(self):
        if self.on_open_dir:
            self.on_open_dir()

    def _open_file(self):
        if self.on_open_file:
            self.on_open_file()

    def _open_recent(self, path: str, kind: str):
        if self.on_open_recent:
            self.on_open_recent(path, kind)

    def _save_view(self):
        if self.on_save_view:
            self.on_save_view()

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

    def _histogram(self):
        if self.on_histogram:
            self.on_histogram()

    def _show_shortcuts(self):
        if self.on_show_shortcuts:
            self.on_show_shortcuts()

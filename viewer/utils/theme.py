from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

DARK = {
    "bg": "#2b2b2b",
    "bg_light": "#3c3c3c",
    "bg_darker": "#1e1e1e",
    "fg": "#d4d4d4",
    "fg_dim": "#808080",
    "accent": "#4a9eff",
    "select_bg": "#264f78",
    "info_bg": "#1e3a5f",
}

LIGHT = {
    "bg": "#f0f0f0",
    "bg_light": "#ffffff",
    "bg_darker": "#d9d9d9",
    "fg": "#1e1e1e",
    "fg_dim": "#6e6e6e",
    "accent": "#0078d4",
    "select_bg": "#cce4ff",
    "info_bg": "#d6eaf8",
}

PALETTES = {"dark": DARK, "light": LIGHT}

# ---------------------------------------------------------------------------
# Theme manager
# ---------------------------------------------------------------------------

_current_theme = "dark"
_current_font_size = 10
_current_font_weight = "normal"


def get_current_theme() -> str:
    return _current_theme


def get_current_font_size() -> int:
    return _current_font_size


def get_current_font_weight() -> str:
    return _current_font_weight


def apply_theme(root: tk.Tk, name: str = "dark") -> None:
    """Apply the named theme (dark or light) to the entire app."""
    global _current_theme
    _current_theme = name
    p = PALETTES[name]
    style = ttk.Style(root)

    root.configure(bg=p["bg"])
    root.option_add("*Background", p["bg"])
    root.option_add("*Foreground", p["fg"])
    root.option_add("*selectBackground", p["select_bg"])
    root.option_add("*selectForeground", p["fg"])

    style.theme_use("clam")

    # General
    style.configure(".", background=p["bg"], foreground=p["fg"],
                     fieldbackground=p["bg_light"], bordercolor=p["bg_light"],
                     troughcolor=p["bg_darker"],
                     selectbackground=p["select_bg"], selectforeground=p["fg"])

    # Frames
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabelframe", background=p["bg"], foreground=p["fg"])
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])

    # Labels
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("Info.TLabel", background=p["info_bg"], foreground=p["fg"])
    style.configure("Info.TFrame", background=p["info_bg"])

    # Buttons
    style.configure("TButton", background=p["bg_light"], foreground=p["fg"], padding=4)
    style.map("TButton",
              background=[("active", p["select_bg"]), ("disabled", p["bg_darker"])],
              foreground=[("disabled", p["fg_dim"])])

    # Combobox
    style.configure("TCombobox", fieldbackground=p["bg_light"], foreground=p["fg"],
                     background=p["bg_light"], selectbackground=p["select_bg"])
    style.map("TCombobox", fieldbackground=[("readonly", p["bg_light"])])

    # Entry
    style.configure("TEntry", fieldbackground=p["bg_light"], foreground=p["fg"])

    # Treeview
    style.configure("Treeview", background=p["bg_light"], foreground=p["fg"],
                     fieldbackground=p["bg_light"], rowheight=22)
    style.configure("Treeview.Heading", background=p["bg_darker"], foreground=p["fg"])
    style.map("Treeview", background=[("selected", p["select_bg"])])

    # Scrollbar
    style.configure("TScrollbar", background=p["bg_light"], troughcolor=p["bg_darker"],
                     bordercolor=p["bg_darker"], arrowcolor=p["fg"])

    # Separator
    style.configure("TSeparator", background=p["fg_dim"])

    # tk.Scale
    root.option_add("*Scale.background", p["bg"])
    root.option_add("*Scale.foreground", p["fg"])
    root.option_add("*Scale.troughColor", p["bg_darker"])
    root.option_add("*Scale.highlightBackground", p["bg"])
    root.option_add("*Scale.highlightThickness", 0)

    # Menu
    root.option_add("*Menu.background", p["bg_light"])
    root.option_add("*Menu.foreground", p["fg"])
    root.option_add("*Menu.activeBackground", p["select_bg"])
    root.option_add("*Menu.activeForeground", p["fg"])
    root.option_add("*Menu.borderWidth", 1)

    # Status bar (tk.Label)
    root.option_add("*Label.background", p["bg"])
    root.option_add("*Label.foreground", p["fg"])

    # Re-apply font with current settings
    apply_font(root, _current_font_size, _current_font_weight)


def apply_font(root: tk.Tk, size: int | None = None, weight: str | None = None) -> None:
    """Apply font size and/or weight globally. Preserves current value for unset params."""
    global _current_font_size, _current_font_weight
    if size is not None:
        _current_font_size = size
    if weight is not None:
        _current_font_weight = weight
    size = _current_font_size
    weight = _current_font_weight

    # Update all named fonts — auto-propagates to widgets referencing them
    for name in ("TkDefaultFont", "TkTextFont", "TkFixedFont",
                 "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(name).configure(size=size, weight=weight)
        except tk.TclError:
            pass

    # Update ttk styles
    default_font = tkfont.nametofont("TkDefaultFont")
    style = ttk.Style(root)
    font_tuple = (default_font.cget("family"), size, weight)
    style.configure(".", font=font_tuple)
    style.configure("Treeview", font=font_tuple, rowheight=int(size * 2.2))
    style.configure("Treeview.Heading", font=(default_font.cget("family"), size, "bold"))

    # Force font on all existing tk widgets (named font changes don't always
    # propagate on all platforms, e.g. WSL2/X11)
    _apply_font_recursive(root, font_tuple)


def _apply_font_recursive(widget: tk.Widget, font_tuple: tuple) -> None:
    """Walk the widget tree and explicitly set font on every widget that supports it."""
    try:
        widget.configure(font=font_tuple)
    except tk.TclError:
        pass  # widget doesn't support font option
    for child in widget.winfo_children():
        _apply_font_recursive(child, font_tuple)

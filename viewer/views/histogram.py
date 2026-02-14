from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class HistogramWindow:
    """Histogram window showing intensity distribution in linear and log scale."""

    def __init__(self, master: tk.Toplevel, data: np.ndarray, title: str = ""):
        self.master = master
        self.master.title("Histogram" + (f" — {title}" if title else ""))
        self.master.geometry("700x500")

        self._data = data.ravel()
        self._bins = 256

        # Controls frame
        ctrl = ttk.Frame(master)
        ctrl.pack(fill=tk.X, padx=8, pady=(8, 0))

        ttk.Label(ctrl, text="Bins:").pack(side=tk.LEFT, padx=(0, 4))
        self._bins_var = tk.IntVar(value=256)
        bins_combo = ttk.Combobox(
            ctrl, textvariable=self._bins_var,
            values=[64, 128, 256, 512, 1024], state="readonly", width=6,
        )
        bins_combo.pack(side=tk.LEFT, padx=2)
        bins_combo.bind("<<ComboboxSelected>>", lambda _: self._update())

        ttk.Separator(ctrl, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8
        )

        # Stats
        mn, mx = float(np.min(self._data)), float(np.max(self._data))
        mean = float(np.mean(self._data))
        std = float(np.std(self._data))
        stats_text = f"Min: {mn:.1f}  Max: {mx:.1f}  Mean: {mean:.1f}  Std: {std:.1f}"
        ttk.Label(ctrl, text=stats_text).pack(side=tk.LEFT, padx=4)

        # Matplotlib figure with two subplots
        self._fig = Figure(figsize=(7, 4.5), dpi=100)
        self._fig.set_facecolor("#2b2b2b")
        self._ax_lin = self._fig.add_subplot(211)
        self._ax_log = self._fig.add_subplot(212)

        self._canvas_widget = FigureCanvasTkAgg(self._fig, master=master)
        self._canvas_widget.get_tk_widget().pack(
            fill=tk.BOTH, expand=True, padx=8, pady=8
        )

        self._update()

    def _update(self) -> None:
        self._bins = self._bins_var.get()

        for ax in (self._ax_lin, self._ax_log):
            ax.clear()
            ax.set_facecolor("#1e1e1e")
            ax.tick_params(colors="#d4d4d4", labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#3c3c3c")

        # Linear scale
        self._ax_lin.hist(
            self._data, bins=self._bins, color="#4a9eff",
            edgecolor="#2b2b2b", linewidth=0.3, alpha=0.85,
        )
        self._ax_lin.set_title("Linear Scale", color="#d4d4d4", fontsize=10)
        self._ax_lin.set_ylabel("Count", color="#d4d4d4", fontsize=9)

        # Logarithmic scale
        self._ax_log.hist(
            self._data, bins=self._bins, color="#4a9eff",
            edgecolor="#2b2b2b", linewidth=0.3, alpha=0.85,
        )
        self._ax_log.set_yscale("log")
        self._ax_log.set_title("Logarithmic Scale", color="#d4d4d4", fontsize=10)
        self._ax_log.set_xlabel("Intensity", color="#d4d4d4", fontsize=9)
        self._ax_log.set_ylabel("Count (log)", color="#d4d4d4", fontsize=9)

        self._fig.tight_layout()
        self._canvas_widget.draw()

    def update_data(self, data: np.ndarray) -> None:
        """Update histogram with new slice data."""
        self._data = data.ravel()
        self._update()

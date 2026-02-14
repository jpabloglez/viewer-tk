from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

import nibabel as nib
import pydicom

logger = logging.getLogger(__name__)


class MetadataWindow:
    """Unified metadata viewer for DICOM and NIfTI with search, copy,
    and horizontal scrollbar."""

    def __init__(self, master: tk.Toplevel, metadata):
        self.master = master
        self.master.title("Metadata")
        self.master.geometry("750x550")
        self._all_items: list[tuple[str, str, str, str]] = []  # (iid, name, value, vr)

        # --- search bar ---
        search_frame = ttk.Frame(master)
        search_frame.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Label(search_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_filter)
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.focus_set()

        # --- tree + scrollbars ---
        tree_frame = ttk.Frame(master)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.tree = ttk.Treeview(
            tree_frame, columns=("Value", "VR"), show="tree headings"
        )
        self.tree.heading("#0", text="Name")
        self.tree.heading("Value", text="Value")
        self.tree.heading("VR", text="VR")
        self.tree.column("#0", width=250, minwidth=120)
        self.tree.column("Value", width=350, minwidth=100)
        self.tree.column("VR", width=50, stretch=False)

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # --- right-click context menu ---
        self._ctx_menu = tk.Menu(master, tearoff=0)
        self._ctx_menu.add_command(label="Copy Value", command=self._copy_value)
        self.tree.bind("<Button-3>", self._on_right_click)

        self._populate(metadata)

    def _populate(self, metadata) -> None:
        if isinstance(metadata, pydicom.dataset.FileDataset):
            self._populate_dicom("", metadata)
        elif isinstance(metadata, nib.nifti1.Nifti1Image):
            self._populate_nifti(metadata)
        else:
            logger.warning("Unknown metadata type: %s", type(metadata))

    def _populate_dicom(self, parent: str, dataset) -> None:
        for elem in dataset:
            if elem.VR == "SQ":
                iid = self.tree.insert(
                    parent, "end",
                    text=f"{elem.name} ({elem.tag})",
                    values=("Sequence", elem.VR),
                )
                self._all_items.append((iid, elem.name, "Sequence", elem.VR))
                for i, item in enumerate(elem.value):
                    sub = self.tree.insert(iid, "end", text=f"Item {i + 1}")
                    self._populate_dicom(sub, item)
            elif elem.VM > 1:
                value = "\\".join(str(v) for v in elem.value)
                iid = self.tree.insert(
                    parent, "end",
                    text=f"{elem.name} ({elem.tag})",
                    values=(value, elem.VR),
                )
                self._all_items.append((iid, elem.name, value, elem.VR))
            else:
                value = str(elem.value)
                iid = self.tree.insert(
                    parent, "end",
                    text=f"{elem.name} ({elem.tag})",
                    values=(value, elem.VR),
                )
                self._all_items.append((iid, elem.name, value, elem.VR))

    def _populate_nifti(self, nifti_img: nib.nifti1.Nifti1Image) -> None:
        header = nifti_img.header
        for key in header.keys():
            if key == "unused_data":
                continue
            value = str(header[key])
            iid = self.tree.insert(
                "", "end",
                text=str(key),
                values=(value, ""),
            )
            self._all_items.append((iid, str(key), value, ""))

    def _on_filter(self, *_args) -> None:
        query = self._search_var.get().lower()
        if not query:
            # Show all
            for iid, _, _, _ in self._all_items:
                try:
                    self.tree.reattach(iid, self.tree.parent(iid) or "", "end")
                except tk.TclError:
                    pass
            return
        for iid, name, value, vr in self._all_items:
            match = query in name.lower() or query in value.lower() or query in vr.lower()
            try:
                if match:
                    self.tree.reattach(iid, self.tree.parent(iid) or "", "end")
                else:
                    self.tree.detach(iid)
            except tk.TclError:
                pass

    def _on_right_click(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self._ctx_menu.post(event.x_root, event.y_root)

    def _copy_value(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        if values:
            self.master.clipboard_clear()
            self.master.clipboard_append(values[0])

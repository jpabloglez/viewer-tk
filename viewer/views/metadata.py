import logging
import tkinter as tk
from tkinter import ttk

import nibabel as nib
import pydicom

logger = logging.getLogger(__name__)


class MetadataWindow:
    """Unified metadata viewer for DICOM and NIfTI (bug #5 fix: proper imports)."""

    def __init__(self, master: tk.Toplevel, metadata):
        self.master = master
        self.master.title("Metadata")
        self.master.geometry("700x500")

        # TreeView with Name, Value, VR columns
        self.tree = ttk.Treeview(
            master, columns=("Value", "VR"), show="tree headings"
        )
        self.tree.heading("#0", text="Name")
        self.tree.heading("Value", text="Value")
        self.tree.heading("VR", text="VR")
        self.tree.column("VR", width=50, stretch=False)

        scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

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
                node = self.tree.insert(
                    parent, "end",
                    text=f"{elem.name} ({elem.tag})",
                    values=("Sequence", elem.VR),
                )
                for i, item in enumerate(elem.value):
                    sub = self.tree.insert(node, "end", text=f"Item {i + 1}")
                    self._populate_dicom(sub, item)
            elif elem.VM > 1:
                values = "\\".join(str(v) for v in elem.value)
                self.tree.insert(
                    parent, "end",
                    text=f"{elem.name} ({elem.tag})",
                    values=(values, elem.VR),
                )
            else:
                value = str(elem.value)
                if len(value) > 80:
                    value = value[:77] + "..."
                self.tree.insert(
                    parent, "end",
                    text=f"{elem.name} ({elem.tag})",
                    values=(value, elem.VR),
                )

    def _populate_nifti(self, nifti_img: nib.nifti1.Nifti1Image) -> None:
        header = nifti_img.header
        for key in header.keys():
            if key == "unused_data":
                continue
            self.tree.insert(
                "", "end",
                text=str(key),
                values=(str(header[key]), ""),
            )

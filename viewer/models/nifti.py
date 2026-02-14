from __future__ import annotations

import logging

import nibabel as nib
import numpy as np

from .base import ImageVolume

logger = logging.getLogger(__name__)


class NiftiVolume(ImageVolume):
    """NIfTI volume — no temp files, direct numpy slicing (bug #6 fix)."""

    def __init__(self):
        self._img: nib.nifti1.Nifti1Image | None = None
        self._data: np.ndarray | None = None

    def load(self, path: str) -> None:
        self._img = nib.load(path)
        self._data = self._img.get_fdata()
        if self._data.ndim < 3:
            raise ValueError(
                f"NIfTI volume must be at least 3D, got {self._data.ndim}D "
                f"with shape {self._data.shape}"
            )
        logger.info(
            "Loaded NIfTI %s — shape %s, dtype %s",
            path, self._data.shape, self._data.dtype,
        )

    def get_slice(self, index: int, axis: int = 2) -> np.ndarray:
        """Return a 2D slice along the given axis (0=sagittal, 1=coronal, 2=axial)."""
        slicing = [slice(None)] * 3
        slicing[axis] = index
        return self._data[tuple(slicing)].astype(np.float64)

    def num_slices(self, axis: int = 2) -> int:
        return self._data.shape[axis]

    def get_metadata(self):
        return self._img

    def get_info_summary(self) -> dict:
        if self._img is None:
            return {}
        header = self._img.header
        return {
            "Dimensions": str(header["dim"][1:4]),
            "Voxel Size": str(header["pixdim"][1:4]),
            "Data Type": str(header.get_data_dtype()),
        }

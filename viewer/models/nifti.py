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
        img = nib.load(path)
        # Reorient to RAS (Right-Anterior-Superior) canonical orientation
        self._img = nib.as_closest_canonical(img)
        self._data = self._img.get_fdata()
        if self._data.ndim < 3:
            raise ValueError(
                f"NIfTI volume must be at least 3D, got {self._data.ndim}D "
                f"with shape {self._data.shape}"
            )
        orig_ornt = nib.aff2axcodes(img.affine)
        canon_ornt = nib.aff2axcodes(self._img.affine)
        logger.info(
            "Loaded NIfTI %s — shape %s, dtype %s, orientation %s → %s (RAS)",
            path, self._data.shape, self._data.dtype,
            "".join(orig_ornt), "".join(canon_ornt),
        )

    def get_slice(self, index: int, axis: int = 2) -> np.ndarray:
        """Return a 2D slice along the given axis (0=sagittal, 1=coronal, 2=axial).

        After RAS canonical reorientation, raw numpy slices need rotation
        to display in standard radiological orientation:
        - Axial (axis=2):    R×A plane → rotate so A is vertical (anterior up)
        - Sagittal (axis=0): A×S plane → rotate so S is vertical (superior up)
        - Coronal (axis=1):  R×S plane → rotate so S is vertical (superior up)
        """
        slicing = [slice(None)] * 3
        slicing[axis] = index
        slice_2d = self._data[tuple(slicing)].astype(np.float64)
        return np.rot90(slice_2d)

    def num_slices(self, axis: int = 2) -> int:
        return self._data.shape[axis]

    def get_metadata(self):
        return self._img

    def get_info_summary(self) -> dict:
        if self._img is None:
            return {}
        header = self._img.header
        ornt = "".join(nib.aff2axcodes(self._img.affine))
        return {
            "Dimensions": str(header["dim"][1:4]),
            "Voxel Size": str(header["pixdim"][1:4]),
            "Data Type": str(header.get_data_dtype()),
            "Orientation": f"{ornt} (RAS canonical)",
        }

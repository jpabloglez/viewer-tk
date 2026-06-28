from __future__ import annotations

import logging

import nibabel as nib
import numpy as np

from .base import ImageVolume

logger = logging.getLogger(__name__)


class NiftiVolume(ImageVolume):
    """NIfTI volume — supports 3D and 4D (time/DWI) data."""

    def __init__(self):
        self._img: nib.nifti1.Nifti1Image | None = None
        self._data: np.ndarray | None = None
        self._n_volumes: int = 1

    def load(self, path: str) -> None:
        img = nib.load(path)
        self._img = nib.as_closest_canonical(img)
        # Keep native float32 — get_fdata() defaults to float64 which can add 8+ seconds
        # for float32 volumes; specifying dtype=float32 avoids that upcast entirely.
        self._data = self._img.get_fdata(dtype=np.float32)
        if self._data.ndim < 3:
            raise ValueError(
                f"NIfTI volume must be at least 3D, got {self._data.ndim}D "
                f"with shape {self._data.shape}"
            )
        self._n_volumes = int(self._data.shape[3]) if self._data.ndim == 4 else 1
        orig_ornt = nib.aff2axcodes(img.affine)  # type: ignore[attr-defined]
        canon_ornt = nib.aff2axcodes(self._img.affine)
        logger.info(
            "Loaded NIfTI %s — shape %s, dtype %s, orientation %s → %s (RAS)",
            path, self._data.shape, self._data.dtype,
            "".join(orig_ornt), "".join(canon_ornt),
        )

    def get_slice(self, index: int, axis: int = 2, *, volume: int = 0) -> np.ndarray:
        """Return a 2D slice along *axis*.

        For 4D data, *volume* selects the timepoint/DWI direction.
        After RAS canonical reorientation, a single rot90 puts superior up in all views.
        """
        if self._data.ndim == 4:
            vol_data = self._data[..., volume]
        else:
            vol_data = self._data
        slicing: list[slice | int] = [slice(None)] * 3
        slicing[axis] = index
        slice_2d = vol_data[tuple(slicing)]
        return np.rot90(slice_2d)

    def num_slices(self, axis: int = 2) -> int:
        return self._data.shape[axis]

    def num_volumes(self) -> int:
        return self._n_volumes

    def get_pixel_spacing(self) -> tuple[float, float] | None:
        if self._img is None:
            return None
        pixdim = self._img.header["pixdim"]
        try:
            return (float(pixdim[1]), float(pixdim[2]))
        except (IndexError, TypeError):
            return None

    def get_metadata(self):
        return self._img

    def get_info_summary(self) -> dict:
        if self._img is None:
            return {}
        header = self._img.header
        ornt = "".join(nib.aff2axcodes(self._img.affine))
        px = header["pixdim"][1:4]
        voxel_str = f"{float(px[0]):.2f} × {float(px[1]):.2f} × {float(px[2]):.2f} mm"
        dims = header["dim"][1:4]
        info: dict = {
            "Dimensions": f"{int(dims[0])} × {int(dims[1])} × {int(dims[2])}",
            "Voxel Size": voxel_str,
            "Data Type": str(header.get_data_dtype()),
            "Orientation": f"{ornt} (RAS canonical)",
        }
        if self._n_volumes > 1:
            info["Volumes"] = str(self._n_volumes)
        return info

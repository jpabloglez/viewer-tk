from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
import pydicom
import pydicom.misc

from .base import ImageVolume

logger = logging.getLogger(__name__)


class DicomVolume(ImageVolume):
    """DICOM directory volume — one file per slice."""

    def __init__(self):
        self._files: list[str] = []
        self._current_ds: pydicom.Dataset | None = None

    def load(self, path: str) -> None:
        """Scan *path* for valid DICOM files, sort by InstanceNumber."""
        self._read_pixel_data.cache_clear()
        candidates = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        ]
        # Bug #4 fix: filter with is_dicom instead of matching all files
        self._files = [f for f in candidates if pydicom.misc.is_dicom(f)]
        if not self._files:
            raise FileNotFoundError(
                f"No valid DICOM files found in '{path}'"
            )
        self._sort_files()
        logger.info("Loaded %d DICOM files from %s", len(self._files), path)

    def _sort_files(self) -> None:
        """Sort by InstanceNumber with fallback to filename."""
        def sort_key(filepath):
            try:
                ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                return int(ds.InstanceNumber)
            except Exception:
                return os.path.basename(filepath)
        self._files.sort(key=sort_key)

    def get_slice(self, index: int, axis: int = 2) -> np.ndarray:
        """Read pixel data for slice *index*, apply rescale slope/intercept."""
        img = self._read_pixel_data(index)
        ds = pydicom.dcmread(self._files[index], stop_before_pixels=True)
        self._current_ds = ds
        if "RescaleSlope" in ds and "RescaleIntercept" in ds:
            img = img.astype(np.float64) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
        return img

    @lru_cache(maxsize=64)
    def _read_pixel_data(self, index: int) -> np.ndarray:
        ds = pydicom.dcmread(self._files[index])
        return ds.pixel_array.astype(np.float64)

    def num_slices(self, axis: int = 2) -> int:
        return len(self._files)

    def get_metadata(self):
        """Return the full DICOM dataset for the current slice."""
        return self._current_ds

    def get_info_summary(self) -> dict:
        ds = self._current_ds
        if ds is None:
            return {}
        return {
            "Patient ID": str(ds.get("PatientID", "N/A")),
            "Patient Age": str(ds.get("PatientAge", "N/A")),
            "Modality": str(ds.get("Modality", "N/A")),
            "Series Description": str(ds.get("SeriesDescription", "N/A")),
        }

    def get_window_defaults(self) -> tuple[float | None, float | None]:
        """Return (center, width) from DICOM tags, or (None, None)."""
        ds = self._current_ds
        if ds is None:
            return None, None
        try:
            center = float(ds.WindowCenter if not isinstance(ds.WindowCenter, pydicom.multival.MultiValue) else ds.WindowCenter[0])
            width = float(ds.WindowWidth if not isinstance(ds.WindowWidth, pydicom.multival.MultiValue) else ds.WindowWidth[0])
            return center, width
        except (AttributeError, TypeError, IndexError):
            return None, None

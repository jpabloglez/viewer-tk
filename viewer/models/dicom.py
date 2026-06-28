from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Callable

import numpy as np
import pydicom
import pydicom.misc

from .base import ImageVolume

logger = logging.getLogger(__name__)


class DicomVolume(ImageVolume):
    """DICOM directory volume — supports single-file-per-slice and multi-frame files."""

    def __init__(self):
        # Each entry is (filepath, frame_index_within_file)
        self._slices: list[tuple[str, int]] = []
        # Per-slice header dataset (read once during sort, reused on every get_slice)
        self._headers: list[pydicom.Dataset | None] = []
        self._current_ds: pydicom.Dataset | None = None

    def load(
        self,
        path: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """Scan *path* for valid DICOM files, sort by InstanceNumber, expand multi-frame.

        *progress_callback(done, total)* is called from the loading thread after each
        header is read. Callers must marshal to the UI thread themselves (e.g. root.after).
        """
        self._read_pixel_data.cache_clear()
        candidates = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        ]
        files = [f for f in candidates if pydicom.misc.is_dicom(f)]
        if not files:
            raise FileNotFoundError(f"No valid DICOM files found in '{path}'")
        self._slices, self._headers = self._expand_and_sort(files, progress_callback)
        logger.info("Loaded %d slices from %s", len(self._slices), path)

    def _expand_and_sort(
        self,
        files: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[tuple[str, int]], list[pydicom.Dataset | None]]:
        """Read all headers once, sort by InstanceNumber, expand multi-frame files."""
        entries: list[tuple[tuple, str, int, pydicom.Dataset | None]] = []
        total = len(files)
        for done, filepath in enumerate(files, 1):
            try:
                ds = pydicom.dcmread(filepath, stop_before_pixels=True)
                n_frames = int(ds.get("NumberOfFrames", 1))
                # Normalised sort key: ints before fallback strings
                if "InstanceNumber" in ds:
                    sort_key: tuple = (0, int(ds.InstanceNumber), "")
                else:
                    sort_key = (1, 0, os.path.basename(filepath))
                header: pydicom.Dataset | None = ds
            except Exception:
                n_frames = 1
                sort_key = (1, 0, os.path.basename(filepath))
                header = None
            for frame_idx in range(n_frames):
                entries.append((sort_key, filepath, frame_idx, header))
            if progress_callback is not None:
                progress_callback(done, total)

        # Stable sort: int InstanceNumber first, then filename fallback
        entries.sort(key=lambda e: e[0])
        slices = [(e[1], e[2]) for e in entries]
        headers = [e[3] for e in entries]
        return slices, headers

    def get_pixel_spacing(self) -> tuple[float, float] | None:
        ds = self._current_ds
        if ds is None:
            return None
        try:
            ps = ds.PixelSpacing
            return (float(ps[0]), float(ps[1]))
        except (AttributeError, IndexError, TypeError):
            return None

    def get_slice(self, index: int, axis: int = 2, *, volume: int = 0) -> np.ndarray:
        """Return pixel data for slice *index*, apply rescale and radiological flip."""
        img = self._read_pixel_data(index)
        ds = self._headers[index]
        if ds is None:
            filepath, _ = self._slices[index]
            ds = pydicom.dcmread(filepath, stop_before_pixels=True)
            self._headers[index] = ds
        self._current_ds = ds
        if "RescaleSlope" in ds and "RescaleIntercept" in ds:
            img = img.astype(np.float64) * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
        # Radiological convention: flip L-R so patient left is on viewer right
        img = np.fliplr(img)
        return img

    @lru_cache(maxsize=64)
    def _read_pixel_data(self, index: int) -> np.ndarray:
        filepath, frame_idx = self._slices[index]
        ds = pydicom.dcmread(filepath)
        arr = ds.pixel_array
        if arr.ndim == 3:
            # Multi-frame: shape (N, H, W)
            return arr[frame_idx].astype(np.float64)
        return arr.astype(np.float64)

    def num_slices(self, axis: int = 2) -> int:
        return len(self._slices)

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
            "Orientation": "LPS (radiological)",
        }

    def get_window_defaults(self) -> tuple[float | None, float | None]:
        """Return (center, width) from DICOM tags, or (None, None)."""
        ds = self._current_ds
        if ds is None:
            return None, None
        try:
            wc = ds.WindowCenter
            center = float(wc[0] if isinstance(wc, pydicom.multival.MultiValue) else wc)
            ww = ds.WindowWidth
            width = float(ww[0] if isinstance(ww, pydicom.multival.MultiValue) else ww)
            return center, width
        except (AttributeError, TypeError, IndexError):
            return None, None

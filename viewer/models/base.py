import logging
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger(__name__)


class ImageVolume(ABC):
    """Abstract base class for medical image volumes."""

    @abstractmethod
    def load(self, path: str) -> None:
        """Load image data from the given path."""

    @abstractmethod
    def get_slice(self, index: int, axis: int = 2) -> np.ndarray:
        """Return a 2D slice as a raw numpy array (no normalization)."""

    @abstractmethod
    def num_slices(self, axis: int = 2) -> int:
        """Return the number of slices along the given axis."""

    @abstractmethod
    def get_metadata(self):
        """Return the raw metadata object for the current slice/volume."""

    @abstractmethod
    def get_info_summary(self) -> dict:
        """Return a dict of key-value pairs for the info bar."""

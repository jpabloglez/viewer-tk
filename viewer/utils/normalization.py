import numpy as np

WINDOW_PRESETS: dict[str, tuple[float, float]] = {
    "Brain": (40.0, 80.0),
    "Bone": (300.0, 1500.0),
    "Lung": (-600.0, 1500.0),
    "Abdomen": (60.0, 400.0),
    "Soft Tissue": (50.0, 350.0),
}


def normalize_min_max(data: np.ndarray) -> np.ndarray:
    """Normalize to uint8 [0, 255]. Returns zeros when min==max (bug #1 fix)."""
    mn, mx = float(np.min(data)), float(np.max(data))
    if mn == mx:
        return np.zeros(data.shape, dtype=np.uint8)
    out = (data - mn) / (mx - mn) * 255.0
    return out.astype(np.uint8)


def apply_window_level(
    data: np.ndarray, center: float, width: float
) -> np.ndarray:
    """Apply DICOM window/level and return uint8."""
    lower = center - width / 2.0
    upper = center + width / 2.0
    out = np.clip((data - lower) / (upper - lower) * 255.0, 0, 255)
    return out.astype(np.uint8)


def apply_colormap(data_uint8: np.ndarray, cmap_name: str = "gray") -> np.ndarray:
    """Apply a matplotlib colormap to a uint8 grayscale array. Returns RGB uint8."""
    if cmap_name == "gray":
        return np.stack([data_uint8] * 3, axis=-1)
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap(cmap_name)
    mapped = cmap(data_uint8 / 255.0)  # returns RGBA float [0,1]
    return (mapped[:, :, :3] * 255).astype(np.uint8)

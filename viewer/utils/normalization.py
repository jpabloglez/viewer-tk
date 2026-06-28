import numpy as np

WINDOW_PRESETS: dict[str, tuple[float, float]] = {
    "Brain": (40.0, 80.0),
    "Bone": (300.0, 1500.0),
    "Lung": (-600.0, 1500.0),
    "Abdomen": (60.0, 400.0),
    "Soft Tissue": (50.0, 350.0),
}


def _build_lut(keypoints: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    """Interpolate a 256-entry RGB LUT from (x: 0.0–1.0, rgb: 0–255) keypoints."""
    xs = np.linspace(0.0, 1.0, 256)
    kx = [p[0] for p in keypoints]
    lut = np.zeros((256, 3), dtype=np.uint8)
    for ch in range(3):
        ky = [p[1][ch] for p in keypoints]
        lut[:, ch] = np.clip(np.interp(xs, kx, ky), 0, 255).astype(np.uint8)
    return lut


_LUT: dict[str, np.ndarray] = {
    "hot": _build_lut([
        (0.000, (0,   0,   0)),
        (0.333, (255, 0,   0)),
        (0.667, (255, 255, 0)),
        (1.000, (255, 255, 255)),
    ]),
    "jet": _build_lut([
        (0.000, (0,   0,   143)),
        (0.125, (0,   0,   255)),
        (0.375, (0,   255, 255)),
        (0.625, (255, 255, 0)),
        (0.875, (255, 0,   0)),
        (1.000, (128, 0,   0)),
    ]),
    "bone": _build_lut([
        (0.000, (0,   0,   0)),
        (0.375, (84,  84,  115)),
        (0.750, (168, 199, 199)),
        (1.000, (255, 255, 255)),
    ]),
}


def normalize_min_max(data: np.ndarray) -> np.ndarray:
    """Normalize to uint8 [0, 255]. Returns zeros when min==max (or NaN/Inf)."""
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    mn, mx = float(np.min(data)), float(np.max(data))
    if mn == mx:
        return np.zeros(data.shape, dtype=np.uint8)
    out = (data - mn) / (mx - mn) * 255.0
    return out.astype(np.uint8)


def apply_window_level(
    data: np.ndarray, center: float, width: float
) -> np.ndarray:
    """Apply DICOM window/level and return uint8. Returns zeros when width <= 0."""
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    if width <= 0:
        return np.zeros(data.shape, dtype=np.uint8)
    lower = center - width / 2.0
    upper = center + width / 2.0
    out = np.clip((data - lower) / (upper - lower) * 255.0, 0, 255)
    return out.astype(np.uint8)


def apply_colormap(data_uint8: np.ndarray, cmap_name: str = "gray") -> np.ndarray:
    """Apply a colormap LUT to a uint8 grayscale array. Returns RGB uint8."""
    if cmap_name == "gray":
        return np.stack([data_uint8] * 3, axis=-1)
    lut = _LUT.get(cmap_name)
    if lut is None:
        return np.stack([data_uint8] * 3, axis=-1)
    return lut[data_uint8]

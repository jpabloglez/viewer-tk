"""Tests for viewer.utils.normalization."""

import numpy as np

from viewer.utils.normalization import (
    WINDOW_PRESETS,
    apply_colormap,
    apply_window_level,
    normalize_min_max,
)


class TestNormalizeMinMax:
    def test_basic_range(self):
        data = np.array([[0.0, 50.0], [100.0, 200.0]])
        result = normalize_min_max(data)
        assert result.dtype == np.uint8
        assert result.min() == 0
        assert result.max() == 255

    def test_uniform_image_returns_zeros(self):
        """Bug #1: min == max should not cause division by zero."""
        data = np.full((10, 10), 42.0)
        result = normalize_min_max(data)
        assert result.dtype == np.uint8
        assert np.all(result == 0)

    def test_single_pixel(self):
        data = np.array([[5.0]])
        result = normalize_min_max(data)
        assert result.shape == (1, 1)
        assert result[0, 0] == 0  # uniform → zeros

    def test_negative_values(self):
        data = np.array([[-100.0, 0.0, 100.0]])
        result = normalize_min_max(data)
        assert result[0, 0] == 0
        assert result[0, 2] == 255

    def test_preserves_shape(self):
        data = np.random.rand(64, 128)
        result = normalize_min_max(data)
        assert result.shape == (64, 128)

    def test_already_uint8_range(self):
        data = np.array([[0.0, 255.0]])
        result = normalize_min_max(data)
        assert result[0, 0] == 0
        assert result[0, 1] == 255


class TestApplyWindowLevel:
    def test_basic_window(self):
        data = np.array([[0.0, 40.0, 80.0]])
        result = apply_window_level(data, center=40.0, width=80.0)
        assert result.dtype == np.uint8
        assert result[0, 0] == 0
        assert result[0, 1] == 127  # center maps to ~127
        assert result[0, 2] == 255

    def test_values_below_window_clamp_to_zero(self):
        data = np.array([[-1000.0]])
        result = apply_window_level(data, center=40.0, width=80.0)
        assert result[0, 0] == 0

    def test_values_above_window_clamp_to_255(self):
        data = np.array([[5000.0]])
        result = apply_window_level(data, center=40.0, width=80.0)
        assert result[0, 0] == 255

    def test_brain_preset(self):
        center, width = WINDOW_PRESETS["Brain"]
        data = np.array([[center]])
        result = apply_window_level(data, center, width)
        # Center value should map to ~127
        assert 120 <= result[0, 0] <= 135

    def test_all_presets_exist(self):
        expected = {"Brain", "Bone", "Lung", "Abdomen", "Soft Tissue"}
        assert set(WINDOW_PRESETS.keys()) == expected


class TestApplyColormap:
    def test_gray_returns_3channel(self):
        data = np.array([[0, 128, 255]], dtype=np.uint8)
        result = apply_colormap(data, "gray")
        assert result.shape == (1, 3, 3)
        assert result.dtype == np.uint8
        # Gray: all channels equal
        assert np.all(result[0, 0] == 0)
        assert np.all(result[0, 2] == 255)

    def test_hot_colormap(self):
        data = np.zeros((4, 4), dtype=np.uint8)
        result = apply_colormap(data, "hot")
        assert result.shape == (4, 4, 3)
        assert result.dtype == np.uint8

    def test_jet_colormap(self):
        data = np.full((2, 2), 128, dtype=np.uint8)
        result = apply_colormap(data, "jet")
        assert result.shape == (2, 2, 3)

    def test_preserves_shape(self):
        data = np.random.randint(0, 256, (32, 64), dtype=np.uint8)
        result = apply_colormap(data, "gray")
        assert result.shape == (32, 64, 3)

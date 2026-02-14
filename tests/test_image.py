"""Tests for viewer.utils.image."""

from PIL import Image

from viewer.utils.image import resize_to_fit


class TestResizeToFit:
    def test_landscape_image(self):
        img = Image.new("RGB", (200, 100))
        result = resize_to_fit(img, 100, 100)
        assert result.width == 100
        assert result.height == 50

    def test_portrait_image(self):
        img = Image.new("RGB", (100, 200))
        result = resize_to_fit(img, 100, 100)
        assert result.width == 50
        assert result.height == 100

    def test_square_image(self):
        img = Image.new("RGB", (200, 200))
        result = resize_to_fit(img, 100, 100)
        assert result.width == 100
        assert result.height == 100

    def test_already_fits(self):
        img = Image.new("RGB", (50, 50))
        result = resize_to_fit(img, 100, 100)
        # Should still resize (to fill available space)
        assert result.width == 100
        assert result.height == 100

    def test_zero_max_width_returns_original(self):
        img = Image.new("RGB", (100, 100))
        result = resize_to_fit(img, 0, 100)
        assert result.width == 100
        assert result.height == 100

    def test_zero_max_height_returns_original(self):
        img = Image.new("RGB", (100, 100))
        result = resize_to_fit(img, 100, 0)
        assert result.width == 100
        assert result.height == 100

    def test_negative_dims_returns_original(self):
        img = Image.new("RGB", (100, 100))
        result = resize_to_fit(img, -10, -10)
        assert result.width == 100

    def test_aspect_ratio_preserved(self):
        img = Image.new("RGB", (300, 100))
        result = resize_to_fit(img, 150, 200)
        ratio_orig = img.width / img.height
        ratio_result = result.width / result.height
        assert abs(ratio_orig - ratio_result) < 0.1

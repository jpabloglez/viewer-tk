"""Tests for viewer.models.nifti.NiftiVolume."""

import os
import tempfile

import nibabel as nib
import numpy as np
import pytest

from viewer.models.nifti import NiftiVolume


def _create_nifti(shape=(10, 12, 14), affine=None, path=None):
    """Create a temporary NIfTI file with known data."""
    data = np.random.rand(*shape).astype(np.float32)
    if affine is None:
        affine = np.eye(4)
    img = nib.Nifti1Image(data, affine)
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".nii.gz")
        os.close(fd)
    nib.save(img, path)
    return path, data


class TestNiftiLoad:
    def test_load_valid_file(self, tmp_path):
        path, _ = _create_nifti(path=str(tmp_path / "test.nii.gz"))
        vol = NiftiVolume()
        vol.load(path)
        assert vol.num_slices(axis=2) > 0

    def test_load_reorients_to_ras(self, tmp_path):
        # Create a non-RAS image (e.g., LPS orientation)
        affine = np.diag([-1, -1, 1, 1])  # LPS
        path, _ = _create_nifti(shape=(8, 10, 12), affine=affine,
                                path=str(tmp_path / "lps.nii.gz"))
        vol = NiftiVolume()
        vol.load(path)
        # After canonical reorientation, should be RAS
        ornt = nib.aff2axcodes(vol._img.affine)
        assert "".join(ornt) == "RAS"

    def test_load_2d_raises(self, tmp_path):
        data = np.random.rand(10, 10).astype(np.float32)
        img = nib.Nifti1Image(data, np.eye(4))
        path = str(tmp_path / "flat.nii.gz")
        nib.save(img, path)
        vol = NiftiVolume()
        with pytest.raises(ValueError, match="at least 3D"):
            vol.load(path)

    def test_load_nonexistent_raises(self):
        vol = NiftiVolume()
        with pytest.raises(Exception):
            vol.load("/nonexistent/path.nii")


class TestNiftiSlicing:
    @pytest.fixture()
    def volume(self, tmp_path):
        path, data = _create_nifti(shape=(8, 10, 12),
                                   path=str(tmp_path / "vol.nii.gz"))
        vol = NiftiVolume()
        vol.load(path)
        return vol

    def test_num_slices_per_axis(self, volume):
        # After RAS reorientation with identity affine, shape is preserved
        assert volume.num_slices(axis=0) == 8
        assert volume.num_slices(axis=1) == 10
        assert volume.num_slices(axis=2) == 12

    def test_get_slice_returns_2d(self, volume):
        s = volume.get_slice(0, axis=2)
        assert s.ndim == 2

    def test_get_slice_dtype_float64(self, volume):
        s = volume.get_slice(0, axis=0)
        assert s.dtype == np.float64

    def test_get_slice_rotated(self, volume):
        """After rot90, dimensions should be swapped compared to raw slicing."""
        # Axial slice (axis=2): raw would be (8, 10), rot90 gives (10, 8)
        s = volume.get_slice(0, axis=2)
        assert s.shape == (10, 8)

    def test_all_axes_return_slices(self, volume):
        for axis in (0, 1, 2):
            s = volume.get_slice(0, axis=axis)
            assert s.ndim == 2
            assert s.size > 0


class TestNiftiMetadata:
    @pytest.fixture()
    def volume(self, tmp_path):
        path, _ = _create_nifti(shape=(8, 10, 12),
                                path=str(tmp_path / "vol.nii.gz"))
        vol = NiftiVolume()
        vol.load(path)
        return vol

    def test_get_metadata_returns_nifti_image(self, volume):
        meta = volume.get_metadata()
        assert isinstance(meta, nib.Nifti1Image)

    def test_info_summary_keys(self, volume):
        info = volume.get_info_summary()
        assert "Dimensions" in info
        assert "Voxel Size" in info
        assert "Data Type" in info
        assert "Orientation" in info

    def test_info_summary_orientation_contains_ras(self, volume):
        info = volume.get_info_summary()
        assert "RAS" in info["Orientation"]

    def test_info_summary_empty_before_load(self):
        vol = NiftiVolume()
        assert vol.get_info_summary() == {}

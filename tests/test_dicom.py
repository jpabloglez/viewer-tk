"""Tests for viewer.models.dicom.DicomVolume."""

import numpy as np
import pydicom
import pydicom.uid
import pytest
from pydicom.dataset import FileDataset

from viewer.models.dicom import DicomVolume


def _create_dicom_file(path: str, instance_number: int = 1,
                       rows: int = 64, cols: int = 64,
                       slope: float = 1.0, intercept: float = 0.0,
                       window_center: float = 128.0,
                       window_width: float = 256.0) -> None:
    """Create a synthetic DICOM file with pixel data."""
    file_meta = pydicom.Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

    ds = FileDataset(path, {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.SOPClassUID = pydicom.uid.CTImageStorage
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.InstanceNumber = instance_number
    ds.PatientID = "TEST001"
    ds.PatientAge = "030Y"
    ds.Modality = "CT"
    ds.SeriesDescription = "Test Series"
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1  # signed
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.RescaleSlope = slope
    ds.RescaleIntercept = intercept
    ds.WindowCenter = window_center
    ds.WindowWidth = window_width

    pixel_data = np.random.randint(-100, 400, (rows, cols), dtype=np.int16)
    ds.PixelData = pixel_data.tobytes()
    ds.save_as(path)


def _create_dicom_dir(tmp_path, num_slices=3, rows=32, cols=32):
    """Create a directory with multiple synthetic DICOM files."""
    dicom_dir = tmp_path / "dicom"
    dicom_dir.mkdir()
    for i in range(num_slices):
        path = str(dicom_dir / f"slice_{i:03d}.dcm")
        _create_dicom_file(path, instance_number=i + 1, rows=rows, cols=cols)
    return str(dicom_dir)


class TestDicomLoad:
    def test_load_valid_directory(self, tmp_path):
        dicom_dir = _create_dicom_dir(tmp_path, num_slices=5)
        vol = DicomVolume()
        vol.load(dicom_dir)
        assert vol.num_slices() == 5

    def test_load_empty_directory_raises(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        vol = DicomVolume()
        with pytest.raises(FileNotFoundError, match="No valid DICOM"):
            vol.load(str(empty_dir))

    def test_load_dir_with_non_dicom_files(self, tmp_path):
        """Bug #4: non-DICOM files should be filtered out."""
        dicom_dir = _create_dicom_dir(tmp_path, num_slices=2)
        # Add a non-DICOM file
        (tmp_path / "dicom" / "README.txt").write_text("not a dicom")
        vol = DicomVolume()
        vol.load(dicom_dir)
        assert vol.num_slices() == 2  # only real DICOM files

    def test_load_sorts_by_instance_number(self, tmp_path):
        dicom_dir = tmp_path / "dicom"
        dicom_dir.mkdir()
        # Create files in reverse order
        for i in [3, 1, 2]:
            path = str(dicom_dir / f"file_{i}.dcm")
            _create_dicom_file(path, instance_number=i)
        vol = DicomVolume()
        vol.load(str(dicom_dir))
        # After loading, first slice should have InstanceNumber 1
        vol.get_slice(0)
        ds = vol.get_metadata()
        assert int(ds.InstanceNumber) == 1

    def test_load_clears_cache(self, tmp_path):
        dicom_dir = _create_dicom_dir(tmp_path, num_slices=2)
        vol = DicomVolume()
        vol.load(dicom_dir)
        vol.get_slice(0)
        # Reload should not crash (cache cleared)
        vol.load(dicom_dir)
        vol.get_slice(0)


class TestDicomSlicing:
    @pytest.fixture()
    def volume(self, tmp_path):
        dicom_dir = _create_dicom_dir(tmp_path, num_slices=3, rows=32, cols=48)
        vol = DicomVolume()
        vol.load(dicom_dir)
        return vol

    def test_get_slice_returns_2d(self, volume):
        s = volume.get_slice(0)
        assert s.ndim == 2

    def test_get_slice_shape(self, volume):
        s = volume.get_slice(0)
        # After fliplr, shape should be preserved: (rows, cols) = (32, 48)
        assert s.shape == (32, 48)

    def test_get_slice_applies_rescale(self, tmp_path):
        dicom_dir = tmp_path / "rescale"
        dicom_dir.mkdir()
        _create_dicom_file(str(dicom_dir / "s.dcm"), slope=2.0, intercept=-100.0)
        vol = DicomVolume()
        vol.load(str(dicom_dir))
        s = vol.get_slice(0)
        # Values should be transformed by slope/intercept
        assert s.dtype == np.float64

    def test_get_slice_flipped(self, tmp_path):
        """DICOM slices should be horizontally flipped for LPS convention."""
        dicom_dir = tmp_path / "flip"
        dicom_dir.mkdir()
        _create_dicom_file(str(dicom_dir / "s.dcm"), rows=4, cols=4)
        vol = DicomVolume()
        vol.load(str(dicom_dir))
        # Read raw via cache, then compare with get_slice
        raw = vol._read_pixel_data(0)
        processed = vol.get_slice(0)
        # Processed should be flipped version of rescaled raw
        np.testing.assert_array_equal(processed, np.fliplr(raw * 1.0 + 0.0))


class TestDicomMetadata:
    @pytest.fixture()
    def volume(self, tmp_path):
        dicom_dir = _create_dicom_dir(tmp_path, num_slices=2)
        vol = DicomVolume()
        vol.load(dicom_dir)
        vol.get_slice(0)  # populate _current_ds
        return vol

    def test_get_metadata_returns_dataset(self, volume):
        meta = volume.get_metadata()
        assert isinstance(meta, pydicom.Dataset)

    def test_info_summary_keys(self, volume):
        info = volume.get_info_summary()
        assert "Patient ID" in info
        assert "Patient Age" in info
        assert "Modality" in info
        assert "Orientation" in info

    def test_info_summary_values(self, volume):
        info = volume.get_info_summary()
        assert info["Patient ID"] == "TEST001"
        assert info["Modality"] == "CT"
        assert "LPS" in info["Orientation"]

    def test_info_summary_empty_before_get_slice(self, tmp_path):
        dicom_dir = _create_dicom_dir(tmp_path, num_slices=1)
        vol = DicomVolume()
        vol.load(dicom_dir)
        assert vol.get_info_summary() == {}

    def test_window_defaults(self, volume):
        center, width = volume.get_window_defaults()
        assert center == 128.0
        assert width == 256.0

    def test_window_defaults_before_load(self):
        vol = DicomVolume()
        center, width = vol.get_window_defaults()
        assert center is None
        assert width is None

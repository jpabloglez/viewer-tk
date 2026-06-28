"""Smoke tests for ViewerController and the render pipeline.

These tests require a display (Tk root). They are skipped in headless CI unless
xvfb is available. Run locally or via `xvfb-run python -m pytest`.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

import nibabel as nib
import numpy as np
import pydicom
import pydicom.uid
import pytest
from pydicom.dataset import FileDataset

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_display() -> bool:
    if sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


requires_display = pytest.mark.skipif(
    not _has_display(), reason="No display available (set DISPLAY or use xvfb-run)"
)


def _make_root() -> tk.Tk:
    root = tk.Tk()
    root.withdraw()          # don't show the window
    root.geometry("900x700")
    return root


def _destroy(root: tk.Tk) -> None:
    root.destroy()


def _nifti_file(tmp_path, shape=(10, 12, 14)):
    data = np.random.rand(*shape).astype(np.float32)
    img = nib.Nifti1Image(data, np.eye(4))
    path = str(tmp_path / "vol.nii.gz")
    nib.save(img, path)
    return path


def _dicom_dir(tmp_path, n=3, rows=16, cols=16):
    d = tmp_path / "dcm"
    d.mkdir()
    for i in range(n):
        file_meta = pydicom.Dataset()
        file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        ds = FileDataset(str(d / f"s{i}.dcm"), {}, file_meta=file_meta,
                         preamble=b"\x00" * 128)
        ds.SOPClassUID = pydicom.uid.CTImageStorage
        ds.SOPInstanceUID = pydicom.uid.generate_uid()
        ds.StudyInstanceUID = pydicom.uid.generate_uid()
        ds.SeriesInstanceUID = pydicom.uid.generate_uid()
        ds.InstanceNumber = i + 1
        ds.Rows = rows
        ds.Columns = cols
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelData = np.zeros((rows, cols), dtype=np.uint16).tobytes()
        ds.save_as(str(d / f"s{i}.dcm"))
    return str(d)


# ---------------------------------------------------------------------------
# Controller smoke tests
# ---------------------------------------------------------------------------

@requires_display
class TestControllerInit:
    def test_creates_without_crash(self):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            ViewerController(root)
            root.update()
        finally:
            _destroy(root)

    def test_initial_state(self):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            ctrl = ViewerController(root)
            assert ctrl._model is None
            assert not ctrl._is_multi_axis
        finally:
            _destroy(root)


@requires_display
class TestControllerDicom:
    def test_load_dicom(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            ctrl = ViewerController(root)
            dicom_dir = _dicom_dir(tmp_path)
            # Simulate background load completing on main thread
            from viewer.models.dicom import DicomVolume
            model = DicomVolume()
            model.load(dicom_dir)
            ctrl._on_directory_loaded(model, dicom_dir)
            root.update()
            assert ctrl._model is model
            assert not ctrl._is_multi_axis
            assert ctrl._model.num_slices() == 3
        finally:
            _destroy(root)

    def test_step_slices(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            from viewer.models.dicom import DicomVolume
            ctrl = ViewerController(root)
            model = DicomVolume()
            model.load(_dicom_dir(tmp_path))
            ctrl._on_directory_loaded(model, str(tmp_path))
            root.update()
            assert ctrl._current_slice == 0
            ctrl._step(1)
            root.update()
            assert ctrl._current_slice == 1
            ctrl._step(-1)
            root.update()
            assert ctrl._current_slice == 0
        finally:
            _destroy(root)

    def test_step_clamps_at_bounds(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            from viewer.models.dicom import DicomVolume
            ctrl = ViewerController(root)
            model = DicomVolume()
            model.load(_dicom_dir(tmp_path, n=3))
            ctrl._on_directory_loaded(model, str(tmp_path))
            root.update()
            ctrl._step(-10)
            root.update()
            assert ctrl._current_slice == 0
        finally:
            _destroy(root)


@requires_display
class TestControllerNifti:
    def test_load_nifti_enters_multi_axis(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            from viewer.models.nifti import NiftiVolume
            ctrl = ViewerController(root)
            model = NiftiVolume()
            model.load(_nifti_file(tmp_path))
            ctrl._on_file_loaded(model, str(tmp_path / "vol.nii.gz"))
            root.update()
            assert ctrl._is_multi_axis
            assert ctrl._multi_canvas is not None
        finally:
            _destroy(root)

    def test_render_all_axes(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            from viewer.models.nifti import NiftiVolume
            ctrl = ViewerController(root)
            model = NiftiVolume()
            model.load(_nifti_file(tmp_path))
            ctrl._on_file_loaded(model, str(tmp_path / "vol.nii.gz"))
            root.update()
            # All three axes should have cached raw data after render
            assert 0 in ctrl._last_raw_per_axis
            assert 1 in ctrl._last_raw_per_axis
            assert 2 in ctrl._last_raw_per_axis
        finally:
            _destroy(root)

    def test_open_file_threaded_path_renders(self, tmp_path):
        """Regression: the full open_file → worker thread → queue → poller path must
        update the UI. Worker threads cannot call root.after() directly (silently
        dropped on Tcl 9.0); this guards that the queue marshalling actually delivers.
        """
        import time

        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            ctrl = ViewerController(root)
            path = _nifti_file(tmp_path)
            ctrl.open_file(path)  # spawns background thread + starts poller
            # Pump the event loop until the poller delivers the result (or time out)
            deadline = time.time() + 10.0
            while time.time() < deadline and not ctrl._is_multi_axis:
                root.update()
                time.sleep(0.02)
            assert ctrl._is_multi_axis, "load never reached the UI (cross-thread after dropped?)"
            assert ctrl._multi_canvas is not None
            assert set(ctrl._last_raw_per_axis) == {0, 1, 2}
            assert not ctrl._progress_bar.winfo_ismapped()  # progress bar hidden on completion
        finally:
            _destroy(root)

    def test_crosshair_click_updates_slices(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            from viewer.models.nifti import NiftiVolume
            ctrl = ViewerController(root)
            model = NiftiVolume()
            model.load(_nifti_file(tmp_path, shape=(20, 22, 24)))
            ctrl._on_file_loaded(model, str(tmp_path / "vol.nii.gz"))
            root.update()
            # Click at pixel (5, 3) in axial panel → should update sagittal and coronal
            ctrl._on_crosshair_click(clicked_axis=2, img_x=5, img_y=3)
            root.update()
            assert ctrl._axis_slices[0] == 5   # sagittal = img_x
            Y = model.num_slices(1)
            assert ctrl._axis_slices[1] == (Y - 1) - 3  # coronal = (Y-1) - img_y
        finally:
            _destroy(root)


@requires_display
class TestRenderPipeline:
    def test_apply_pipeline_gray(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            ctrl = ViewerController(root)
            raw = np.random.rand(64, 64).astype(np.float64) * 200
            img = ctrl._apply_pipeline(raw)
            from PIL import Image
            assert isinstance(img, Image.Image)
            assert img.size == (64, 64)
        finally:
            _destroy(root)

    def test_apply_pipeline_windowed(self, tmp_path):
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            ctrl = ViewerController(root)
            ctrl._window_center = 100.0
            ctrl._window_width = 200.0
            raw = np.linspace(0, 200, 64 * 64).reshape(64, 64)
            img = ctrl._apply_pipeline(raw)
            assert img.size == (64, 64)
        finally:
            _destroy(root)

    def test_save_view_no_model(self, tmp_path, monkeypatch):
        import tkinter.messagebox as mb
        root = _make_root()
        try:
            from viewer.controllers.viewer import ViewerController
            shown = []
            monkeypatch.setattr(mb, "showinfo", lambda *a, **kw: shown.append(a))
            ctrl = ViewerController(root)
            ctrl.save_view()
            root.update()
            assert shown  # messagebox was shown
        finally:
            _destroy(root)

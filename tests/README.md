# Tests

Unit tests for the `viewer` package using [pytest](https://docs.pytest.org/).

## Setup

Install test dependencies:

```bash
pip install -e ".[test]"
```

Or install pytest directly:

```bash
pip install pytest pytest-cov
```

## Running Tests

Run the full suite:

```bash
python -m pytest tests/ -v
```

Run with coverage report:

```bash
python -m pytest tests/ -v --cov=viewer --cov-report=term-missing
```

Run a single test file:

```bash
python -m pytest tests/test_normalization.py -v
```

Run a specific test class or method:

```bash
python -m pytest tests/test_dicom.py::TestDicomLoad::test_load_valid_directory -v
```

## Lint

```bash
ruff check viewer/ tests/
```

## Test Modules

### `test_normalization.py`

Tests for `viewer.utils.normalization`:

- **`TestNormalizeMinMax`** — min-max normalization to uint8. Covers normal ranges, uniform images (division-by-zero guard), negative values, single pixels, and shape preservation.
- **`TestApplyWindowLevel`** — DICOM windowing with center/width. Covers standard windowing, clamping below/above range, and preset values (Brain, Bone, Lung, Abdomen, Soft Tissue).
- **`TestApplyColormap`** — grayscale passthrough and matplotlib colormaps (hot, jet). Verifies output shape (H, W, 3) and uint8 dtype.

### `test_image.py`

Tests for `viewer.utils.image`:

- **`TestResizeToFit`** — aspect-ratio-preserving resize. Covers landscape, portrait, and square images, zero/negative target dimensions (guard returns original), and aspect ratio preservation.

### `test_nifti.py`

Tests for `viewer.models.nifti.NiftiVolume`:

- **`TestNiftiLoad`** — loading valid files, RAS canonical reorientation (verifies non-RAS input is reoriented), rejection of 2D volumes, and nonexistent path handling.
- **`TestNiftiSlicing`** — per-axis slice counts, 2D output, float64 dtype, rot90 dimension swap for radiological display, and slicing across all three axes.
- **`TestNiftiMetadata`** — metadata type (Nifti1Image), info summary keys (Dimensions, Voxel Size, Data Type, Orientation), RAS label in orientation, and empty summary before load.

Test data is generated in-memory using `nibabel.Nifti1Image` with random float32 arrays and saved to temporary files via `tmp_path` fixtures.

### `test_dicom.py`

Tests for `viewer.models.dicom.DicomVolume`:

- **`TestDicomLoad`** — loading valid directories, empty directory error, non-DICOM file filtering (bug #4 regression), InstanceNumber sorting, and LRU cache clearing on reload.
- **`TestDicomSlicing`** — 2D output shape, correct dimensions after LPS flip, RescaleSlope/Intercept application, and horizontal flip verification against raw pixel data.
- **`TestDicomMetadata`** — Dataset return type, info summary keys and values (Patient ID, Modality, LPS orientation), empty summary before first `get_slice()`, and WindowCenter/WindowWidth defaults.

Test data is generated using `pydicom.dataset.FileDataset` with synthetic CT image attributes and random int16 pixel arrays.

## Test Data Strategy

All tests use **synthetic data** created at runtime — no sample files are committed to the repository:

- **NIfTI**: `nibabel.Nifti1Image` with numpy random arrays and configurable affine matrices
- **DICOM**: `pydicom.dataset.FileDataset` with standard CT attributes, written to `tmp_path` fixtures

This ensures tests are self-contained, fast, and run without external data dependencies.

## CI

Tests run automatically on push/PR to `main` via GitHub Actions (`.github/workflows/ci.yml`):

- Lint: `ruff check viewer/ tests/`
- Test: `pytest tests/ -v --cov=viewer` on Python 3.10, 3.11, 3.12

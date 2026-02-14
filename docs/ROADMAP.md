# Medical Image Viewer — Roadmap

## Current State

The project is an early-stage prototype with two separate entry points (`image-viewer.py` and `viewer.py`) that duplicate most functionality. It supports basic DICOM and NIfTI slice viewing with a Tkinter GUI, but has significant gaps in robustness, architecture, and features.

---

## Phase 1: Stabilization & Bug Fixes

These are issues that cause crashes or incorrect behavior today.

### Bugs

- **Division by zero in normalization** (`image-viewer.py:198`, `241`): `(max - min)` can be zero for uniform images, causing a crash. `viewer.py:327` handles this correctly — the fix exists but isn't applied in the main file.
- **Unreachable code** (`viewer.py:322`): `get_slice()` returns raw data and never calls `normalize_slice()`, so the matplotlib viewer shows unnormalized images.
- **Slider always uses NIfTI path** (`image-viewer.py:103`): `self.image_format` is `None` at construction time, so the `if self.image_format == "DICOM"` branch is never taken. The DICOM slider is never created correctly.
- **File filter catches everything** (`image-viewer.py:145`): `f.endswith(('', '.dcm'))` — empty string matches all files, so non-DICOM files (READMEs, hidden files) get loaded and crash sorting.
- **Missing `messagebox` import** (`viewer.py:213`): `tk.messagebox.showinfo()` will raise `AttributeError` since `messagebox` is imported from `tkinter` but accessed on the `tk` module.
- **Temp files never cleaned** (`viewer.py:355`): `NiftiImage` creates a temp directory and renders all slices to PNG but `NiftiViewerMpl` never calls cleanup if closed unexpectedly.

### Missing dependencies in `requirements.txt`

- `matplotlib` (used in `viewer.py`)
- `numpy` (used everywhere)
- `Pillow` (used everywhere)
- `tkinter` should be removed (it's part of the standard library and `pip install tkinter` fails)

---

## Phase 2: Architecture Refactor

The two files share ~60% identical code. Consolidate into a clean structure.

### Proposed layout

```
viewer/
├── __main__.py          # Entry point, argparse
├── app.py               # Application setup (Tk root, main window)
├── models/
│   ├── base.py          # Abstract base: ImageVolume
│   ├── dicom.py         # DicomVolume (load dir, sort, get slice, metadata)
│   └── nifti.py         # NiftiVolume (load file, get slice, metadata)
├── views/
│   ├── canvas.py        # Image canvas with resize logic
│   ├── metadata.py      # Metadata TreeView window
│   ├── toolbar.py       # Button bar
│   └── info_bar.py      # Patient/image info panel
├── controllers/
│   └── viewer.py        # Orchestration: binds model ↔ views
└── utils/
    ├── normalization.py  # Window/level, min-max, etc.
    └── image.py          # PIL resize helpers
```

### Key principles

- **Separate data from UI**: `ImageVolume` classes know nothing about Tkinter. They load data, return numpy arrays and metadata dicts.
- **Single responsibility**: Each view handles one piece of the UI. The controller wires them together.
- **Eliminate duplication**: One `update_slice` path that delegates to the model for data and the view for rendering.
- **Format-agnostic interface**: `ImageVolume.get_slice(index) -> np.ndarray` and `ImageVolume.get_metadata() -> dict` work the same for DICOM and NIfTI.

---

## Phase 3: Robustness

### Error handling

- Wrap file I/O in try/except: corrupted DICOM files, permission errors, missing tags.
- Handle missing `InstanceNumber` gracefully (fall back to filename sort).
- Validate pixel data before normalization (check dtype, shape, NaN/Inf values).
- Show user-facing error dialogs instead of crashing silently.

### Logging

- Replace all `print()` calls with `logging` module.
- Add debug-level logging for slice loads, metadata parsing, file discovery.

### Threading

- Move file I/O off the main thread. Loading a DICOM directory reads every file header for sorting — this blocks the UI for large series.
- Use `threading.Thread` + `root.after()` pattern for Tkinter-safe async updates.
- Show a progress indicator during directory loading.

### Input validation

- Validate DICOM directory contents before attempting sort (filter to actual DICOM files using `pydicom.misc.is_dicom`).
- Bounds-check slice index against file list length.
- Handle canvas width/height of 0 at startup (before first layout pass).

---

## Phase 4: Core Feature Additions

### Window/Level (Windowing)

The README mentions this but it's not implemented. This is the single most important feature for a medical image viewer.

- Add Window Center / Window Width controls (sliders or text input).
- Read default values from DICOM tags `(0028,1050)` and `(0028,1051)`.
- Common presets: Bone, Lung, Brain, Abdomen, Soft Tissue.
- Replace the current min-max normalization with proper windowing: `output = ((pixel - (center - width/2)) / width) * 255`, clamped to [0, 255].

### Zoom & Pan

- Mouse wheel zoom centered on cursor position.
- Click-and-drag pan.
- "Fit to window" and "1:1 pixel" reset buttons.
- Display current zoom level.

### Multi-axis NIfTI viewing

- Show axial, sagittal, and coronal views simultaneously (3-panel layout).
- Crosshair linking: clicking in one view updates the slice position in the other two.

### Caching

- Cache decoded pixel arrays for recently viewed slices (LRU, configurable size).
- Avoid re-reading DICOM files when navigating back and forth.

### Colormap support

- Grayscale (default), hot, jet, bone colormaps.
- Dropdown or toggle in the toolbar.

---

## Phase 5: UI Improvements

### Internationalization

- Currently mixed Spanish/English. Pick one language for the UI (English recommended for medical software) and apply consistently.
- Move all user-facing strings to a constants file for future i18n.

### Layout polish

- Use a proper status bar at the bottom showing: slice number, image dimensions, pixel value under cursor, zoom level.
- Add a menu bar: File (Open DICOM Dir, Open NIfTI, Recent Files, Exit), View (Metadata, Reset Zoom), Tools (Window Presets).
- Keyboard shortcuts: `Ctrl+O` open, `Ctrl+M` metadata, `Home/End` first/last slice, `Ctrl+0` reset zoom.

### Metadata viewer improvements

- Add search/filter in the metadata TreeView.
- Copy tag value to clipboard on right-click.
- Show tag group descriptions.
- Horizontal scrollbar for long values (instead of truncating at 50 chars).

### Dark theme

- Medical images are viewed on dark backgrounds. Add a dark theme option using `ttk` theme configuration or `sv_ttk`.

---

## Phase 6: Testing & CI

### Unit tests

- Model layer: test DICOM/NIfTI loading, sorting, metadata extraction, normalization edge cases.
- Utils: test windowing math, resize calculations.
- Use `pytest` with synthetic DICOM files (pydicom can generate test datasets) and small NIfTI volumes (nibabel can create them in memory).

### Integration tests

- Test full load → display → navigate flow using Tkinter's `.update()` in headless mode.

### CI pipeline

- GitHub Actions: lint (`ruff`), type check (`mypy`), test (`pytest`), with Python 3.9–3.12 matrix.

### Packaging

- Add `pyproject.toml` with proper dependency declarations.
- Entry point: `python -m viewer` or installable script.
- Optional: PyInstaller or cx_Freeze config for standalone executable.

---

## Phase 7: Advanced Features (longer-term)

- **Annotations**: Draw ROIs (rectangles, ellipses, freehand), measure distances and angles, persist annotations as overlays.
- **Image comparison**: Side-by-side or overlay mode for comparing two series/timepoints.
- **DICOM networking**: Query/Retrieve from PACS using `pynetdicom`.
- **3D rendering**: Volume rendering or maximum intensity projection using VTK or napari integration.
- **Export**: Save current view as PNG/JPEG, export slice range, generate reports.
- **Plugin system**: Allow loading custom processing modules (filters, segmentation algorithms) at runtime.

---

## Suggested Priority Order

| Priority | Item | Impact |
|----------|------|--------|
| 1 | Fix crashes (Phase 1) | Users can't use the tool if it crashes |
| 2 | Consolidate duplicate code | Reduces maintenance burden for everything else |
| 3 | Window/Level controls | Most critical missing feature for clinical use |
| 4 | Error handling + threading | Prevents freezes and data-dependent crashes |
| 5 | Zoom & Pan | Basic expected functionality |
| 6 | Multi-axis NIfTI views | Major usability improvement for volumetric data |
| 7 | UI polish (menus, dark theme, i18n) | Professional appearance |
| 8 | Tests + CI + packaging | Long-term maintainability |
| 9 | Advanced features (Phase 7) | Differentiation, broader use cases |

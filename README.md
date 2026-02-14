# Medical Image Viewer

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Application for medical imaging pixel and metadata visualization.

## Features

- DICOM directory loading and slice navigation
- NIfTI file loading with multi-axis viewing (axial, sagittal, coronal)
- Window/level presets (Brain, Bone, Lung, Abdomen, Soft Tissue)
- Colormap selection (gray, hot, jet, bone)
- Zoom (scroll wheel) and pan (middle-click drag)
- Metadata viewer with DICOM sequence expansion and NIfTI header display
- Keyboard navigation (Left/Right arrows, Home/End)

## Project Structure

```
viewer/
├── __init__.py
├── __main__.py          # CLI entry point
├── app.py               # Tk root setup
├── controllers/
│   └── viewer.py        # Main controller
├── models/
│   ├── base.py          # ImageVolume ABC
│   ├── dicom.py         # DicomVolume
│   └── nifti.py         # NiftiVolume
├── views/
│   ├── canvas.py        # Single image canvas with zoom/pan
│   ├── info_bar.py      # Data-driven info bar
│   ├── metadata.py      # Metadata window (DICOM + NIfTI)
│   ├── multi_canvas.py  # 3-panel multi-axis view
│   └── toolbar.py       # Toolbar with controls
└── utils/
    ├── image.py          # Resize utilities
    └── normalization.py  # Normalize, windowing, colormaps
```

## Prerequisites

- Python 3.9 or higher

## Installation

1. Clone the repository:
```bash
git clone https://github.com/jpabloglez/image-viewer.git
cd image-viewer
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

```bash
# Open a DICOM directory
python -m viewer -d /path/to/dicom/directory

# Open a NIfTI file
python -m viewer -i /path/to/file.nii

# Launch without arguments (use Open Dir / Open File buttons)
python -m viewer

# Enable debug logging
python -m viewer -d /path/to/dicom --log-level DEBUG
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

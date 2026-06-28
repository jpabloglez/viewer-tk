"""User-visible UI strings — single source of truth for status and dialog messages."""

# Window title
APP_TITLE = "Medical Image Viewer"

# Status bar
STATUS_READY = "Ready"
STATUS_LOAD_FAILED = "Load failed"

# Loading messages
def status_loading_dicom(path: str) -> str:
    return f"Loading DICOM: {path}..."

def status_loading_nifti(path: str) -> str:
    return f"Loading NIfTI: {path}..."

def status_loaded_dicom(path: str, n_slices: int) -> str:
    return f"DICOM: {path} — {n_slices} slices"

def status_loaded_nifti(path: str, x: int, y: int, z: int) -> str:
    return f"NIfTI: {path} — {x}×{y}×{z}"

def status_scanning_dicom(done: int, total: int) -> str:
    return f"Scanning DICOM headers: {done}/{total}…"

def status_saved(path: str) -> str:
    return f"Saved: {path}"

# Measure tool
STATUS_MEASURE_START = "Measure: click first point on image"
STATUS_MEASURE_SECOND = "Measure: click second point"

def status_measure_mm(dist: float) -> str:
    return f"Distance: {dist:.2f} mm  (click again to reset)"

def status_measure_px(dist: float) -> str:
    return f"Distance: {dist:.1f} px  (no spacing info — click again to reset)"

# Dialog messages
MSG_LOAD_IMAGE_FIRST = "Load an image first."
MSG_NO_METADATA = "No metadata available."
MSG_NO_IMAGE_RENDERED = "No image rendered yet."

def msg_load_failed(path: str) -> str:
    return f"Failed to load:\n{path}"

# Keyboard shortcuts overlay
SHORTCUTS: list[tuple[str, str]] = [
    ("Ctrl+O",          "Open DICOM directory"),
    ("Ctrl+Shift+O",    "Open NIfTI file"),
    ("Ctrl+S",          "Save current view as PNG/JPEG"),
    ("Ctrl+M",          "Show metadata browser"),
    ("Ctrl+H",          "Show histogram"),
    ("Ctrl+0",          "Reset zoom"),
    ("Ctrl+Q",          "Exit"),
    ("Left / Right",    "Previous / next slice"),
    ("Home / End",      "First / last slice"),
    ("Scroll wheel",    "Zoom in / out"),
    ("Middle-drag",     "Pan image"),
    ("Right-drag",      "Adjust window/level (↑↓ center, ←→ width)"),
    ("Left-click*",     "Place measurement point (*when Measure is on)"),
    ("?",               "Show this shortcuts overlay"),
]

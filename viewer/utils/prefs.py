from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULTS: dict = {
    "colormap": "gray",
}


def _config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "neuro-viewer-tk" / "prefs.json"


def load_prefs() -> dict:
    path = _config_path()
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(path.read_text())
        prefs = dict(_DEFAULTS)
        prefs.update({k: v for k, v in data.items() if k in _DEFAULTS})
        return prefs
    except Exception:
        logger.debug("Failed to read prefs", exc_info=True)
        return dict(_DEFAULTS)


def save_prefs(prefs: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        to_save = {k: prefs[k] for k in _DEFAULTS if k in prefs}
        path.write_text(json.dumps(to_save, indent=2))
    except Exception:
        logger.debug("Failed to write prefs", exc_info=True)

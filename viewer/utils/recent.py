from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_RECENT = 10


def _config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "neuro-viewer-tk" / "recent.json"


def load_recent() -> list[dict]:
    path = _config_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [item for item in data if isinstance(item, dict)][:_MAX_RECENT]
    except Exception:
        logger.debug("Failed to read recent files", exc_info=True)
        return []


def add_recent(file_path: str, kind: str) -> None:
    """Prepend *file_path* to the recent list (kind: 'dir' or 'file', max 10)."""
    items = [i for i in load_recent() if i.get("path") != file_path]
    items.insert(0, {
        "path": file_path,
        "kind": kind,
        "name": os.path.basename(file_path.rstrip("/\\")),
    })
    config = _config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    try:
        config.write_text(json.dumps(items[:_MAX_RECENT], indent=2))
    except Exception:
        logger.debug("Failed to write recent files", exc_info=True)

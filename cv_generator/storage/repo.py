"""Reading and writing of the JSON files that persist the application state."""

import json
import os
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    """Loads a JSON document from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    """Writes a JSON document atomically.

    The content is first written to a temporary file in the same directory and only
    then moved over the target with os.replace, which is atomic within the same file
    system. An interruption mid-write (killed process, full disk) leaves the target
    intact in its previous version instead of truncated.
    """
    content = json.dumps(data, ensure_ascii=False, indent=2)
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise

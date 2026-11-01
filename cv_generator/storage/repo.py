"""Reading and writing of the JSON files that persist the application state."""

import json
import os
import tempfile
import time
from os import close as _close_fd
from pathlib import Path
from typing import Any

# Waits between attempts to replace a file another program holds; replaced in tests.
_sleep = time.sleep
_REPLACE_WAITS = (0.05, 0.1, 0.2, 0.4)


def read_json(path: Path) -> dict[str, Any]:
    """Loads a JSON document from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    """Writes a JSON document atomically.

    The content is first written to a temporary file in the same directory and only
    then moved over the target with os.replace, which is atomic within the same file
    system. An interruption mid-write (killed process, full disk) leaves the target
    intact in its previous version instead of truncated.

    On Windows, antivirus, OneDrive or the search indexer can hold the target for a
    moment and make os.replace raise PermissionError, so that one error is retried a
    few times (under a second in all) before giving up.
    """
    content = json.dumps(data, ensure_ascii=False, indent=2)
    # A name of its own per save: two tabs saving the same file must not share one.
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    _close_fd(descriptor)
    temp_path = Path(temp_name)
    try:
        temp_path.write_text(content, encoding="utf-8")
        for wait in _REPLACE_WAITS:
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                _sleep(wait)
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise

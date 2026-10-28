"""Interaction with the operating system from the interface."""

import subprocess
import sys
from pathlib import Path

# Viewer per platform. It is a fixed table: the user never chooses the command.
VIEWERS = {"darwin": "/usr/bin/open", "win32": "start"}
DEFAULT_VIEWER = "xdg-open"


def open_with_viewer(path: Path, allowed_dir: Path) -> None:
    """Opens a file with the system viewer.

    The path comes from the history, which is a hand-editable JSON file, so it is
    required to point inside the output directory before handing it to the operating
    system.

    Raises:
        ValueError: if the path points outside the allowed directory.
        FileNotFoundError: if the file does not exist.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_dir.resolve()):
        raise ValueError(f"the path points outside the allowed directory: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"the file no longer exists: {resolved}")

    command = VIEWERS.get(sys.platform, DEFAULT_VIEWER)
    subprocess.run([command, str(resolved)], check=False)  # noqa: S603

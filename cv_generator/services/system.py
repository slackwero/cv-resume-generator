"""Interaction with the operating system from the interface."""

import os
import subprocess
import sys
from pathlib import Path

# Viewer per platform. It is a fixed table: the user never chooses the command.
# Windows is not in it: `start` is a cmd built-in, not a program, so it opens the file
# with os.startfile instead.
VIEWERS = {"darwin": "/usr/bin/open"}
DEFAULT_VIEWER = "xdg-open"


class ViewerUnavailable(Exception):
    """The system viewer could not be started. It is not a missing file."""


def open_with_viewer(path: Path, allowed_dir: Path, platform: str = sys.platform) -> None:
    """Opens a file with the system viewer.

    The path comes from the history, which is a hand-editable JSON file, so it is
    required to point inside the output directory before handing it to the operating
    system.

    Raises:
        ValueError: if the path points outside the allowed directory.
        FileNotFoundError: if the file does not exist.
        ViewerUnavailable: if the viewer could not be started; the OSError is its cause.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_dir.resolve()):
        raise ValueError(f"the path points outside the allowed directory: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"the file no longer exists: {resolved}")

    try:
        if platform == "win32":
            os.startfile(resolved)  # type: ignore[attr-defined]  # noqa: S606
        else:
            command = VIEWERS.get(platform, DEFAULT_VIEWER)
            subprocess.run([command, str(resolved)], check=False)  # noqa: S603
    except OSError as error:
        raise ViewerUnavailable(f"the PDF viewer could not be started: {error}") from error

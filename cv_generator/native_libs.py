"""Environment setup for the native libraries WeasyPrint uses.

WeasyPrint loads pango, cairo and glib through dlopen, and on macOS the dynamic linker
does not look in the Homebrew directories. The variable has to be set before the
process's first weasyprint import: preloading with ctypes does not work, because
WeasyPrint asks for the libraries by a name that does not match their install_name.

That is why it is called from `cv_generator/__init__.py`: this way it is solved for
everyone who uses the package, not only for whoever goes through the renderer.
"""

import os
import sys
from pathlib import Path

MACOS_LIBRARY_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")


def prepare_native_libraries() -> None:
    """Exposes the Homebrew libraries to the dynamic linker. Idempotent."""
    if sys.platform != "darwin":
        return

    current_path = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    directories = [directory for directory in current_path.split(":") if directory]
    directories += [
        directory for directory in MACOS_LIBRARY_DIRS if Path(directory).is_dir() and directory not in directories
    ]
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(directories)

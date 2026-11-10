"""Keeps what the app writes readable only by the account that runs it.

The profile, the CVs, the PDF previews and the sessions Reflex saves to disk (which carry
the loaded profile, photo included) are personal data. With the usual umask, 022, they
came out readable by every other account on the computer: 0644 files in 0755 folders.
"""

import contextlib
import os
from collections.abc import Iterable
from pathlib import Path

import reflex as rx
from reflex.utils.prerequisites import get_states_dir

from cv_generator.app.config import DATA_DIR, OUTPUT_DIR

# From then on, 0600 files and 0700 folders, for everything the backend writes.
PRIVATE_UMASK = 0o077
PRIVATE_FOLDER = 0o700


def keep_private(folders: Iterable[Path]) -> None:
    """Makes what is written from now on private, and closes the folders already holding data.

    Closing a folder covers the files already inside, whatever their own mode: another
    account cannot go in to read them. A folder that cannot be closed is left as it is: the
    app still works. On Windows the user's own folders are already private, and these
    modes do not apply.
    """
    if os.name == "nt":
        return
    os.umask(PRIVATE_UMASK)
    for folder in folders:
        if folder.is_dir():
            with contextlib.suppress(OSError):
                folder.chmod(PRIVATE_FOLDER)


def keep_app_files_private() -> None:
    """Closes the app's folders with personal data when the backend starts.

    A lifespan task and not an import: the tests import the app, and would close the real
    folders and change the umask of the whole run. `.states` is where Reflex saves the
    sessions.
    """
    keep_private([DATA_DIR, OUTPUT_DIR, rx.get_upload_dir(), get_states_dir()])

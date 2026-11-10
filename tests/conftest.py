from pathlib import Path

import pytest

from cv_generator.app.states import (
    experience_state,
    home_state,
    profile_state,
    sync_state,
    text_list_state,
    wizard_state,
)

# Each state module imports `DATA_DIR` by name, so each one is pointed at the folder.
STATE_MODULES = (
    experience_state,
    home_state,
    profile_state,
    sync_state,
    text_list_state,
    wizard_state,
)


@pytest.fixture(autouse=True)
def screen_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data folder of its own for the states, never the real `data/`.

    For every test and not only the ones that ask for it: a test that runs a handler
    and forgets it would write over the owner's profile when run from the main checkout.
    """
    for module in STATE_MODULES:
        monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The folder Reflex serves at `/_upload`, of its own for every test, never the real one.

    `rx.get_upload_dir()` reads the variable on every call.
    """
    folder = tmp_path / "uploaded_files"
    monkeypatch.setenv("REFLEX_UPLOADED_FILES_DIR", str(folder))
    return folder

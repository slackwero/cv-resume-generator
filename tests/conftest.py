from pathlib import Path

import pytest

from cv_generator.app.states import experience_state, profile_state, sync_state, wizard_state

# Each state module imports `DATA_DIR` by name, so each one is pointed at the folder.
STATE_MODULES = (experience_state, profile_state, sync_state, wizard_state)


@pytest.fixture
def screen_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data folder of its own for the states under test, never the real `data/`."""
    for module in STATE_MODULES:
        monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    return tmp_path

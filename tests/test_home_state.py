from pathlib import Path

import pytest

from cv_generator.app.states import home_state
from cv_generator.app.states.home_state import HomeState
from cv_generator.services.system import ViewerUnavailable
from tests.screens import new_state, run


def _open_failing_with(error: Exception, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> HomeState:
    def fail(path: Path, allowed_dir: Path) -> None:
        raise error

    monkeypatch.setattr(home_state, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(home_state, "open_with_viewer", fail)
    state = new_state(HomeState)
    run(HomeState.open_pdf, state, str(tmp_path / "cv.pdf"))
    return state


def test_a_viewer_that_cannot_start_is_not_reported_as_a_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    try:
        raise FileNotFoundError(2, "No such file")
    except FileNotFoundError as cause:
        unavailable = ViewerUnavailable("no viewer")
        unavailable.__cause__ = cause

    state = _open_failing_with(unavailable, monkeypatch, tmp_path)

    assert state.message.startswith("Your PDF viewer could not be opened")
    assert "cv.pdf" in state.message
    assert "no longer in output/" not in state.message


def test_a_file_that_is_gone_keeps_its_own_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _open_failing_with(FileNotFoundError("gone"), monkeypatch, tmp_path)

    assert "cv.pdf is no longer in output/" in state.message

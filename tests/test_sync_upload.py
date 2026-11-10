"""What the sync screen does with the file you upload.

The export is a file someone hands you: whatever it holds, the screen says what went
wrong and the box takes another file.
"""

import io
from pathlib import Path

import pytest
import reflex as rx

from cv_generator.app.states import sync_state
from cv_generator.app.states.sync_state import SyncState
from cv_generator.services.sync import AnalysisResult
from tests.screens import new_state, run


def _upload(name: str, content: bytes) -> rx.UploadFile:
    return rx.UploadFile(file=io.BytesIO(content), path=Path(name), size=len(content))


@pytest.fixture
def screen() -> SyncState:
    state = new_state(SyncState)
    run(SyncState.start, state)
    return state


def test_a_file_the_parser_chokes_on_is_said_and_frees_the_box(screen: SyncState) -> None:
    """zipfile raises its own BadZipFile, which is not a ValueError nor an OSError."""
    run(SyncState.process_file, screen, [_upload("export.zip", b"not a zip")])

    assert screen.error_message.startswith("The LinkedIn export could not be read: ")
    assert not screen.analyzing


def test_a_bug_after_reading_still_frees_the_box(screen: SyncState, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bug is not the file's fault: it is raised, so Reflex reports it, but the box is freed."""

    def fail(*_: object) -> None:
        raise RuntimeError("a bug")

    monkeypatch.setattr(sync_state, "analyze_file", lambda *_: AnalysisResult())
    monkeypatch.setattr(sync_state, "summary_by_kind", fail)

    with pytest.raises(RuntimeError):
        run(SyncState.process_file, screen, [_upload("export.zip", b"PK")])

    assert not screen.analyzing


def test_opening_the_screen_frees_a_box_left_analyzing(screen: SyncState) -> None:
    """The state outlives a reload: a box stuck by an older failure is freed by opening the screen."""
    screen.analyzing = True

    run(SyncState.start, screen)

    assert not screen.analyzing

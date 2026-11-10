"""What the sync screen does with the file you upload.

The export is a file someone hands you: whatever it holds, the screen says what went
wrong and the box takes another file.
"""

import io
import stat
import sys
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


def test_the_export_is_read_from_a_private_copy_deleted_afterwards(
    screen: SyncState, upload_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It holds your personal data, and Reflex serves its upload folder at /_upload to whoever asks."""
    read_from: list[Path] = []

    def analyze_file(path: Path, _: object) -> AnalysisResult:
        assert path.read_bytes() == b"PK export"
        if sys.platform != "win32":
            assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        read_from.append(path)
        return AnalysisResult()

    monkeypatch.setattr(sync_state, "analyze_file", analyze_file)

    run(SyncState.process_file, screen, [_upload("export.zip", b"PK export")])

    assert len(read_from) == 1
    assert not read_from[0].is_relative_to(upload_dir)
    assert not read_from[0].exists()
    assert not upload_dir.exists() or not any(upload_dir.iterdir())


def test_opening_the_screen_deletes_the_copy_older_versions_left(upload_dir: Path) -> None:
    upload_dir.mkdir()
    for name in ("export_linkedin.pdf", "export_linkedin.zip"):
        (upload_dir / name).write_bytes(b"an old export")

    run(SyncState.start, new_state(SyncState))

    assert list(upload_dir.iterdir()) == []

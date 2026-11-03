import errno
from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.app.states import home_state
from cv_generator.app.states.home_state import HomeState
from cv_generator.models.cv import CVContent, GeneratedCV, Selection
from cv_generator.services.generation import load_cv, save_cv
from cv_generator.services.preferences import load_content_language, save_content_language
from cv_generator.services.profile import save_profile
from cv_generator.services.system import ViewerUnavailable
from cv_generator.services.translations import save_translation, text_key
from cv_generator.storage.history import register_cv
from tests.bilingual import sample_profile
from tests.screens import new_state, run
from tests.test_models_personal import REQUIRED


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


def _regenerate_failing_with(error: Exception, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> HomeState:
    def fail(data_dir: Path, output_dir: Path, cv_id: str) -> Path:
        raise error

    monkeypatch.setattr(home_state, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(home_state, "rewrite_pdf", fail)
    state = new_state(HomeState)
    run(HomeState.regenerate, state, "abc")
    return state


def test_regenerating_a_pdf_open_in_a_viewer_says_to_close_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    locked = PermissionError(errno.EACCES, "Permission denied", str(tmp_path / "cv.pdf"))

    state = _regenerate_failing_with(locked, monkeypatch, tmp_path)

    assert state.message.startswith("The PDF could not be rebuilt:")
    assert state.message.endswith("If the PDF is open in a viewer, close it and try again.")
    assert state.regenerating == ""


def test_regenerating_with_a_full_disk_gets_no_viewer_hint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    full = OSError(errno.ENOSPC, "No space left on device", str(tmp_path / "cv.pdf"))

    state = _regenerate_failing_with(full, monkeypatch, tmp_path)

    assert state.message == "The PDF could not be rebuilt: the disk is full"


def test_a_missing_viewer_program_is_not_reported_as_a_system_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    try:
        raise FileNotFoundError(2, "No such file or directory", "xdg-open")
    except FileNotFoundError as cause:
        unavailable = ViewerUnavailable("no viewer")
        unavailable.__cause__ = cause

    state = _open_failing_with(unavailable, monkeypatch, tmp_path)

    assert "no program to open PDFs was found" in state.message
    assert "the system said" not in state.message


def _home_with_a_cv(data_dir: Path) -> tuple[HomeState, str]:
    cv = GeneratedCV(
        created=datetime(2026, 10, 27, 9, 0),  # noqa: DTZ001
        cv_name="Northwind",
        target_role="DevSecOps Engineer",
        language="en",
        template="sidebar",
        pdf_file=str(data_dir / "northwind.pdf"),
        selection=Selection(),
        content=CVContent(personal=REQUIRED),
    )
    save_cv(data_dir, cv)
    register_cv(data_dir, cv)
    state = new_state(HomeState)
    run(HomeState.load, state)
    run(HomeState.start_rename, state, cv.cv_id)
    return state, cv.cv_id


def test_leaving_the_name_field_saves_the_new_name(screen_data: Path) -> None:
    state, cv_id = _home_with_a_cv(screen_data)

    run(HomeState.rename, state, cv_id, "  Northwind, platform team ")

    assert state.renaming == ""
    assert state.history[0]["name"] == "Northwind, platform team"
    assert load_cv(screen_data, cv_id).cv_name == "Northwind, platform team"


def test_enter_saves_the_new_name(screen_data: Path) -> None:
    state, cv_id = _home_with_a_cv(screen_data)

    run(HomeState.rename_from_form, state, {"cv_id": cv_id, "name": "Northwind, platform team"})

    assert state.renaming == ""
    assert state.history[0]["name"] == "Northwind, platform team"


def test_escape_closes_the_field_and_a_late_blur_saves_nothing(screen_data: Path) -> None:
    """Closing the field can still fire its blur with what was typed; that text was cancelled."""
    state, cv_id = _home_with_a_cv(screen_data)

    run(HomeState.escape_rename, state, "Escape")
    run(HomeState.rename, state, cv_id, "Typed and then cancelled")

    assert state.renaming == ""
    assert state.history[0]["name"] == "Northwind"
    assert load_cv(screen_data, cv_id).cv_name == "Northwind"


def test_other_keys_leave_the_field_open(screen_data: Path) -> None:
    state, cv_id = _home_with_a_cv(screen_data)

    run(HomeState.escape_rename, state, "a")

    assert state.renaming == cv_id


def test_a_blank_name_keeps_the_one_it_had(screen_data: Path) -> None:
    state, cv_id = _home_with_a_cv(screen_data)

    run(HomeState.rename, state, cv_id, "   ")

    assert state.renaming == ""
    assert state.message == ""
    assert load_cv(screen_data, cv_id).cv_name == "Northwind"


def test_leaving_the_name_as_it_was_writes_nothing(screen_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state, cv_id = _home_with_a_cv(screen_data)

    def fail(data_dir: Path, cv_id: str, name: str) -> None:
        raise AssertionError("nothing changed, nothing to write")

    monkeypatch.setattr(home_state, "rename_cv", fail)

    run(HomeState.rename, state, cv_id, "Northwind")

    assert state.renaming == ""


def test_a_name_that_cannot_be_saved_says_so_and_keeps_the_old_one(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, cv_id = _home_with_a_cv(screen_data)

    def full(data_dir: Path, cv_id: str, name: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device", str(data_dir / "cvs" / ".tmp"))

    monkeypatch.setattr(home_state, "rename_cv", full)

    run(HomeState.rename, state, cv_id, "Northwind, platform team")

    assert state.message == "The name could not be saved: the disk is full"
    assert state.history[0]["name"] == "Northwind"


def test_a_cv_whose_record_is_gone_cannot_be_renamed(screen_data: Path) -> None:
    state, cv_id = _home_with_a_cv(screen_data)
    (screen_data / "cvs" / f"{cv_id}.json").unlink()

    run(HomeState.rename, state, cv_id, "Northwind, platform team")

    assert state.message == "That CV's record was not found, so its name cannot be changed."


def _profile_on_disk() -> None:
    save_profile(home_state.DATA_DIR, sample_profile())


def test_home_opens_in_the_remembered_language() -> None:
    _profile_on_disk()
    save_content_language(home_state.DATA_DIR, "es")
    state = new_state(HomeState)

    run(HomeState.load, state)

    assert state.language == "es"


def test_home_opens_in_the_source_language_when_nothing_is_remembered() -> None:
    _profile_on_disk()
    state = new_state(HomeState)

    run(HomeState.load, state)

    assert state.language == sample_profile().source_language


def test_switching_saves_the_language_and_recounts() -> None:
    save_profile(home_state.DATA_DIR, save_translation(sample_profile(), "es", text_key("ach-1", "text"), "Texto"))
    state = new_state(HomeState)
    run(HomeState.load, state)

    run(HomeState.switch_language, state, "es")

    assert state.language == "es"
    assert state.pending_summary == "ES · 5 pending translation"
    assert load_content_language(home_state.DATA_DIR) == "es"


def test_nothing_pending_reads_so() -> None:
    profile = sample_profile()
    save_profile(home_state.DATA_DIR, profile)
    state = new_state(HomeState)
    run(HomeState.load, state)

    run(HomeState.switch_language, state, profile.source_language)

    assert state.pending_summary == f"{profile.source_language.upper()} · nothing pending"


def test_an_unknown_language_is_ignored() -> None:
    _profile_on_disk()
    state = new_state(HomeState)
    run(HomeState.load, state)
    before = state.language

    run(HomeState.switch_language, state, "xx")

    assert state.language == before
    assert load_content_language(home_state.DATA_DIR) is None


def test_the_summary_is_empty_without_a_profile() -> None:
    state = new_state(HomeState)

    run(HomeState.load, state)

    assert state.pending_summary == ""


def test_a_language_that_cannot_be_saved_is_still_shown_and_the_failure_is_said(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    save_profile(home_state.DATA_DIR, save_translation(sample_profile(), "es", text_key("ach-1", "text"), "Texto"))
    state = new_state(HomeState)
    run(HomeState.load, state)

    def full(data_dir: Path, language: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(home_state, "save_content_language", full)
    run(HomeState.switch_language, state, "es")

    assert state.language == "es"
    assert state.pending_summary == "ES · 5 pending translation"
    assert state.message.startswith("The language could not be remembered:")

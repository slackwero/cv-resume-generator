"""The sync screen when the profile changes in another tab: what it compares against, and
when applying or undoing refuses so it does not write an old profile over a newer one."""

import asyncio
from pathlib import Path

import pytest

from cv_generator.app.states import sync_state
from cv_generator.app.states.sync_state import PHASE_APPLIED, PHASE_CHOOSE, SyncState
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.sync import AnalysisResult
from tests.screens import new_state, run
from tests.test_models_personal import REQUIRED

EXPORT = Path("Profile.pdf")


def _profile(**fields: str) -> MasterProfile:
    return MasterProfile(personal=PersonalInfo(**{**REQUIRED, **fields}))


@pytest.fixture
def analyzed_against(monkeypatch: pytest.MonkeyPatch) -> list[MasterProfile]:
    """The profiles the importer was handed. It brings no changes: what is tested is the base."""
    seen: list[MasterProfile] = []

    def analyze_file(_: Path, profile: MasterProfile) -> AnalysisResult:
        seen.append(profile)
        return AnalysisResult()

    monkeypatch.setattr(sync_state, "analyze_file", analyze_file)
    return seen


@pytest.fixture
def screen(screen_data: Path, analyzed_against: list[MasterProfile]) -> SyncState:
    """The screen opened over a profile, with an export uploaded and reviewed."""
    save_profile(screen_data, _profile())
    state = new_state(SyncState)
    run(SyncState.start, state)
    asyncio.run(state._analyze(EXPORT))
    return state


def test_the_upload_is_compared_against_the_profile_on_disk_then(
    screen_data: Path, analyzed_against: list[MasterProfile]
) -> None:
    """An edit made after opening the screen and before uploading is part of the review."""
    save_profile(screen_data, _profile())
    state = new_state(SyncState)
    run(SyncState.start, state)
    save_profile(screen_data, _profile(phone="+34 600 000 000"))

    asyncio.run(state._analyze(EXPORT))

    assert analyzed_against[-1].personal.phone == "+34 600 000 000"


def test_a_profile_that_cannot_be_read_at_upload_is_said_and_frees_the_box(
    screen_data: Path, analyzed_against: list[MasterProfile]
) -> None:
    """Raising out of the upload would leave the box stuck on "analyzing"."""
    state = new_state(SyncState)
    run(SyncState.start, state)
    (screen_data / "profile.json").write_text("{ not json", encoding="utf-8")

    asyncio.run(state._analyze(EXPORT))

    assert state.error_message.startswith("Your profile could not be read")
    assert analyzed_against == []


def test_apply_refuses_over_a_profile_changed_after_the_upload(screen: SyncState, screen_data: Path) -> None:
    save_profile(screen_data, _profile(phone="+34 600 000 000"))

    run(SyncState.apply, screen)

    assert screen.phase == PHASE_CHOOSE
    assert screen.error_message.startswith("Your profile changed in another tab after you uploaded the file.")
    on_disk = load_profile(screen_data)
    assert on_disk is not None
    assert on_disk.personal.phone == "+34 600 000 000"


def test_undo_right_after_a_clean_apply_puts_the_profile_back(screen: SyncState) -> None:
    run(SyncState.apply, screen)
    assert screen.phase == PHASE_APPLIED

    run(SyncState.undo, screen)

    assert screen.undone
    assert screen.error_message == ""


def test_a_refused_undo_takes_the_button_away(screen: SyncState, screen_data: Path) -> None:
    """Pressing it again would only refuse again; the backup's name stays on screen."""
    run(SyncState.apply, screen)
    save_profile(screen_data, _profile(phone="+34 600 000 000"))

    run(SyncState.undo, screen)

    assert screen.undo_refused
    assert not screen.undone
    assert screen.error_message.startswith("Your profile changed after this sync")
    assert screen.backup_path != ""
    on_disk = load_profile(screen_data)
    assert on_disk is not None
    assert on_disk.personal.phone == "+34 600 000 000"


def test_a_new_sync_offers_undo_again(screen: SyncState, screen_data: Path) -> None:
    screen.undo_refused = True

    run(SyncState.start, screen)

    assert not screen.undo_refused

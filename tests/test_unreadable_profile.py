"""A profile.json that is not a profile: every screen says so, and none writes over it.

A hand edit with a missing comma, or a file from a newer version of the app, used to
stop the page's own event with a traceback: the page stayed half drawn, and some said
there was no profile yet, which invited a first sync to create one.
"""

import asyncio
from pathlib import Path

import pytest

from cv_generator.app.states.experience_state import ExperienceState
from cv_generator.app.states.home_state import HomeState
from cv_generator.app.states.profile_state import ProfileState
from cv_generator.app.states.sync_state import SyncState
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.services.profile import save_profile
from tests.bilingual import sample_profile
from tests.screens import new_state, run

DAMAGED = b'{"personal": {'
UNREADABLE = "Your profile could not be read: profile.json is not valid JSON"


@pytest.fixture
def damaged(screen_data: Path) -> Path:
    path = screen_data / "profile.json"
    path.write_bytes(DAMAGED)
    return path


def test_home_opens_and_says_why_there_is_no_profile(damaged: Path) -> None:
    home = new_state(HomeState)

    run(HomeState.load, home)
    assert home.message.startswith(UNREADABLE)
    assert not home.has_profile

    run(HomeState.switch_language, home, "es")
    assert home.message.startswith(UNREADABLE)
    assert damaged.read_bytes() == DAMAGED


def test_my_profile_shows_the_notice_instead_of_inviting_an_import(damaged: Path) -> None:
    screen = new_state(ProfileState, "/profile")

    run(ProfileState.start, screen)
    assert screen.profile_error.startswith(UNREADABLE)
    assert not screen.has_profile

    run(ProfileState.refresh_counts, screen)
    run(ProfileState.switch_language, screen, "es")
    assert screen.profile_error.startswith(UNREADABLE)
    assert damaged.read_bytes() == DAMAGED


def test_my_profile_drops_the_notice_once_the_file_is_fixed(damaged: Path, screen_data: Path) -> None:
    screen = new_state(ProfileState, "/profile")
    run(ProfileState.start, screen)

    # The owner puts a good file back; the app itself never writes over a damaged one.
    damaged.unlink()
    save_profile(screen_data, sample_profile())
    run(ProfileState.start, screen)

    assert screen.profile_error == ""
    assert screen.has_profile


def test_work_experience_opens_empty(damaged: Path) -> None:
    editor = new_state(ExperienceState, "/profile?section=experience")
    screen = asyncio.run(editor.get_state(ProfileState))
    run(ProfileState.start, screen)

    run(ExperienceState.start, editor)
    assert not editor.has_profile
    assert editor.error.startswith(UNREADABLE)

    screen.language = "es" if editor.language != "es" else "en"
    run(ExperienceState.show_language, editor)
    assert editor.error.startswith(UNREADABLE)
    assert damaged.read_bytes() == DAMAGED


def test_sync_does_not_offer_to_create_a_profile(damaged: Path) -> None:
    sync = new_state(SyncState, "/sync")

    run(SyncState.start, sync)

    assert sync.error_message.startswith(UNREADABLE)
    assert not sync.is_first_profile
    assert sync.notice == ""


def test_the_wizard_says_why_it_cannot_start(damaged: Path) -> None:
    wizard = new_state(WizardState, "/new")

    run(WizardState.start, wizard)

    assert wizard.message.startswith(UNREADABLE)
    assert damaged.read_bytes() == DAMAGED


def test_the_wizard_buttons_that_read_the_profile_again_keep_what_you_chose(screen_data: Path) -> None:
    """The wizard opened on a good profile, and the file broke while it was open."""
    save_profile(screen_data, sample_profile())
    wizard = new_state(WizardState, "/new")
    run(WizardState.start, wizard)
    chosen = wizard._profile  # noqa: SLF001
    (screen_data / "profile.json").write_bytes(DAMAGED)

    run(WizardState.fetch_profile_photo, wizard)
    assert wizard.photo_notice.startswith(UNREADABLE)
    run(WizardState.fetch_contact_details, wizard)
    assert wizard.contact_notice.startswith(UNREADABLE)
    for handler in (WizardState.update_skills, WizardState.update_achievements, WizardState.update_professions):
        wizard.message = ""
        run(handler, wizard)
        assert wizard.message.startswith(UNREADABLE), handler.fn.__name__

    assert wizard._profile == chosen  # noqa: SLF001
    assert (screen_data / "profile.json").read_bytes() == DAMAGED

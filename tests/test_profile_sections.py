"""The subsections of My profile, and the Contact form across them.

The `section` query value comes from the browser's address bar, so it is checked against
an allowlist: anything that is not exactly a known section opens Contact.
"""

from pathlib import Path

import pytest

from cv_generator.app.pages.profile import _field
from cv_generator.app.states.profile_state import ProfileState, requested_section
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services.profile import load_profile, save_profile
from tests.screens import new_state, run
from tests.test_models_personal import REQUIRED


@pytest.mark.parametrize("name", ["contact", "photo", "skills", "experience"])
def test_a_known_section_is_opened(name: str) -> None:
    assert requested_section(name) == name


@pytest.mark.parametrize("name", ["", "Skills", "admin", "../experience", "experience "])
def test_anything_else_opens_contact(name: str) -> None:
    assert requested_section(name) == "contact"


@pytest.fixture
def screen(screen_data: Path) -> ProfileState:
    save_profile(screen_data, MasterProfile(personal=PersonalInfo(**REQUIRED)))
    state = new_state(ProfileState)
    run(ProfileState.start, state)
    return state


def test_the_address_opens_its_section(screen_data: Path) -> None:
    """A reload, a link from the wizard or Back: `start` reads the section from the address."""
    save_profile(screen_data, MasterProfile(personal=PersonalInfo(**REQUIRED)))
    state = new_state(ProfileState, "/profile?section=experience")

    run(ProfileState.start, state)

    assert state.section == "experience"


def test_opening_a_section_adds_it_to_the_address_bar(screen: ProfileState) -> None:
    """A new step in the history, so Back returns to the subsection before."""
    event = str(run(ProfileState.show_section, screen, "skills"))

    assert screen.section == "skills"
    assert "_redirect" in event
    assert "/profile?section=skills" in event


def test_opening_the_open_section_adds_no_step(screen: ProfileState) -> None:
    assert run(ProfileState.show_section, screen, "contact") is None


def test_an_unknown_section_goes_to_the_address_bar_as_contact(screen: ProfileState) -> None:
    run(ProfileState.show_section, screen, "skills")

    assert "/profile?section=contact" in str(run(ProfileState.show_section, screen, "../admin"))


def test_what_you_typed_and_did_not_save_survives_opening_the_screen_again(
    screen: ProfileState, screen_data: Path
) -> None:
    """Back from another subsection runs `start` again. The untouched fields follow the disk."""
    run(ProfileState.update, screen, "phone", "+34 600 000 000")
    save_profile(screen_data, MasterProfile(personal=PersonalInfo(**{**REQUIRED, "email": "jane@new.example"})))

    run(ProfileState.start, screen)

    assert screen.phone == "+34 600 000 000"
    assert screen.email == "jane@new.example"
    assert screen.has_unsaved_changes


def test_the_form_says_when_it_has_changes_not_saved(screen: ProfileState, screen_data: Path) -> None:
    assert not screen.has_unsaved_changes

    run(ProfileState.update, screen, "country", "Spain ")
    assert screen.has_unsaved_changes

    run(ProfileState.save, screen)
    assert not screen.has_unsaved_changes
    # What it shows is what was written: the trailing space is gone in both.
    assert screen.country == "Spain"
    profile = load_profile(screen_data)
    assert profile is not None
    assert profile.personal.country == "Spain"


def test_typing_the_saved_value_back_is_no_change(screen: ProfileState) -> None:
    run(ProfileState.update, screen, "phone", "+1 555 0199")
    run(ProfileState.update, screen, "phone", REQUIRED["phone"])

    assert not screen.has_unsaved_changes


@pytest.mark.parametrize(("field", "kind"), [("phone", "tel"), ("email", "email"), ("birth_date", "date")])
def test_a_contact_field_buffers_what_you_type(field: str, kind: str) -> None:
    """Each key used to reach the server, and its echo rewrote the field while you typed on:
    "+34 600 333 444" typed fast became "4". Buffered, the field sends what you typed after a
    pause, on Enter and when you leave it, and ignores the echo while you are typing."""
    rendered = str(_field(field, field, getattr(ProfileState, field), kind=kind).render())

    assert "DebounceInput" in rendered
    assert f'"profile-{field}"' in rendered
    assert f'"{kind}"' in rendered

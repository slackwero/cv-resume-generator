"""Completing the contact details the CV would print as PENDING, without losing the half-built CV.

My profile opens in another tab, because going back to /new restarts the wizard. On
return, "Check again" brings in only the contact details.
"""

from pathlib import Path

import pytest

from cv_generator.app.states.wizard_state import WizardState
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services.profile import PENDING_FIELD, save_profile
from tests.screens import new_state, run
from tests.test_models_personal import REQUIRED

PHOTO = "data:image/jpeg;base64,AAAA"


@pytest.fixture
def wizard(screen_data: Path) -> WizardState:
    """A wizard opened over a profile with no phone or profession yet, and a photo."""
    state = new_state(WizardState)
    personal = PersonalInfo(**{**REQUIRED, "phone": PENDING_FIELD, "profession": PENDING_FIELD, "photo": PHOTO})
    state._profile = MasterProfile(personal=personal)
    state.pending = ["profession", "phone"]
    state.header_profession = PENDING_FIELD
    return state


def _complete_on_disk(data_dir: Path, **fields: str) -> None:
    save_profile(data_dir, MasterProfile(personal=PersonalInfo(**{**REQUIRED, **fields})))


def test_check_again_brings_the_completed_details(wizard: WizardState, screen_data: Path) -> None:
    _complete_on_disk(screen_data, phone="+34 600 000 000")

    run(WizardState.fetch_contact_details, wizard)

    assert wizard._profile is not None
    assert wizard._profile.personal.phone == "+34 600 000 000"
    assert wizard.pending == []
    assert wizard.contact_notice == ""


def test_the_photo_stays_as_this_cv_has_it(wizard: WizardState, screen_data: Path) -> None:
    """The photo comes with “I uploaded it”, and the profile on disk has none here."""
    _complete_on_disk(screen_data)

    run(WizardState.fetch_contact_details, wizard)

    assert wizard._profile is not None
    assert wizard._profile.personal.photo == PHOTO


def test_a_header_profession_you_did_not_touch_follows_the_profile(wizard: WizardState, screen_data: Path) -> None:
    _complete_on_disk(screen_data, profession="Software Engineer")

    run(WizardState.fetch_contact_details, wizard)

    assert wizard.header_profession == "Software Engineer"


def test_a_header_profession_you_wrote_for_this_cv_stays(wizard: WizardState, screen_data: Path) -> None:
    wizard.header_profession = "AI Engineer"
    _complete_on_disk(screen_data, profession="Software Engineer")

    run(WizardState.fetch_contact_details, wizard)

    assert wizard.header_profession == "AI Engineer"


def test_what_is_still_missing_is_said(wizard: WizardState, screen_data: Path) -> None:
    _complete_on_disk(screen_data, phone=PENDING_FIELD)

    run(WizardState.fetch_contact_details, wizard)

    assert wizard.pending == ["phone"]
    assert "phone" in wizard.contact_notice
    assert "Check again" in wizard.contact_notice


def test_completing_a_detail_discards_the_preview(wizard: WizardState, screen_data: Path) -> None:
    wizard.pdf_preview = "preview.pdf"
    _complete_on_disk(screen_data)

    run(WizardState.fetch_contact_details, wizard)

    assert wizard.pdf_preview == ""

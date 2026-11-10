"""The ATS badge in the step 1 carousel says what this CV will be, photo included.

`"ats": true` in a meta.json says the parsers read the template's text whole and in order
(tests/test_ats.py). A photo adds no text and several filters drop or reject the document,
so a template that draws one shows the badge only while this CV goes without it.
"""

from pathlib import Path

from cv_generator.app.states.wizard_state import WizardState
from cv_generator.models.profile import MasterProfile
from cv_generator.services.profile import save_profile
from tests import bilingual
from tests.screens import new_state, run
from tests.test_photo import sample_photo

# Reads cleanly and draws the photo; the others with the badge draw none.
WITH_PHOTO = "modern"
WITHOUT_PHOTO = ["direct", "executive", "technical"]


def _open(data_dir: Path, *, photo: bool) -> WizardState:
    profile: MasterProfile = bilingual.sample_profile()
    profile.personal.photo = sample_photo() if photo else None
    save_profile(data_dir, profile)
    state = new_state(WizardState, "/new")
    run(WizardState.start, state)
    return state


def test_a_cv_with_the_photo_has_the_badge_only_where_none_is_drawn(screen_data: Path) -> None:
    wizard = _open(screen_data, photo=True)

    assert wizard.ats_templates == WITHOUT_PHOTO


def test_leaving_the_photo_out_gives_the_badge_to_the_template_that_draws_it(screen_data: Path) -> None:
    wizard = _open(screen_data, photo=True)

    run(WizardState.toggle_photo, wizard, False)

    assert wizard.ats_templates == sorted([*WITHOUT_PHOTO, WITH_PHOTO])


def test_a_profile_without_a_photo_has_the_badge_on_every_template_that_reads_cleanly(screen_data: Path) -> None:
    wizard = _open(screen_data, photo=False)

    assert wizard.ats_templates == sorted([*WITHOUT_PHOTO, WITH_PHOTO])

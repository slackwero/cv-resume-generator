"""Step 2 picks the headline under the name from the list kept in My profile → Contact.

The dropdown shows the entries in the CV's language, a new CV starts with the first usable
one, and a clone keeps the one its CV used: by id, or by text for a recipe made before the
list. A new headline is written in My profile, and "Refresh list" brings it in.
"""

from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.app.components.wizard_steps import application_step
from cv_generator.app.config import DEFAULT_TEMPLATE
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.models.cv import CVContent, GeneratedCV, SelectedExperience, Selection
from cv_generator.models.profile import FIRST_PROFESSION_ID, MasterProfile, Profession
from cv_generator.services.generation import save_cv
from cv_generator.services.preferences import save_content_language
from cv_generator.services.professions import add_profession, edit_profession, remove_profession
from cv_generator.services.profile import PENDING_FIELD, load_profile, save_profile
from cv_generator.services.translations import save_translation, text_key
from tests import bilingual
from tests.screens import new_state, run

PROFESSION = "DevSecOps Engineer"
PROFESSION_ES = "Ingeniera DevSecOps"
ARCHITECT_ID = "p-architect"
ARCHITECT = "Security Architect"
ARCHITECT_ES = "Arquitecta de seguridad"
CLOUD = "Cloud Engineer"
GONE = "The profession this CV used is no longer in your list, so it starts with the first one."


def _profile() -> MasterProfile:
    """The shared sample with a second headline, both translated into Spanish."""
    profile = bilingual.sample_profile()
    profile.professions.append(Profession(id=ARCHITECT_ID, text=ARCHITECT))
    for entry_id, text in ((FIRST_PROFESSION_ID, PROFESSION_ES), (ARCHITECT_ID, ARCHITECT_ES)):
        profile = save_translation(profile, "es", text_key(entry_id, "text"), text)
    return profile


def _open(data_dir: Path, profile: MasterProfile | None = None, address: str = "/new") -> WizardState:
    save_profile(data_dir, profile or _profile())
    state = new_state(WizardState, address)
    run(WizardState.start, state)
    return state


def _on_disk(data_dir: Path) -> MasterProfile:
    profile = load_profile(data_dir)
    assert profile is not None
    return profile


def _listed(state: WizardState) -> list[tuple[str, str, str]]:
    return [(entry["id"], entry["text"], entry["pending"]) for entry in state.professions_list]


def _cv_made_with(data_dir: Path, profile: MasterProfile, selection: Selection, language: str = "es") -> str:
    """A CV generated earlier with this recipe, as the history keeps it; returns its id."""
    cv = GeneratedCV(
        created=datetime(2026, 11, 2, 9, 0),  # noqa: DTZ001
        cv_name="Northwind",
        target_role="DevSecOps Engineer",
        language=language,
        template=DEFAULT_TEMPLATE,
        pdf_file=str(data_dir / "northwind.pdf"),
        selection=selection.model_copy(
            update={"experiences": [SelectedExperience(id="exp-1", achievements=["ach-1"])]}
        ),
        content=CVContent(personal=profile.personal),
    )
    save_cv(data_dir, cv)
    return cv.cv_id


def _clone(data_dir: Path, recipe: Selection, *, made_in: str = "es", now: MasterProfile | None = None) -> WizardState:
    """Clones a CV made with `recipe` over the profile as it is `now` (by default, as it was)."""
    cv_id = _cv_made_with(data_dir, _profile(), recipe, made_in)
    return _open(data_dir, now or _profile(), f"/new?from={cv_id}")


# ------------------------------------------------------------------ a new CV


def test_a_new_cv_starts_with_the_first_usable_profession(screen_data: Path) -> None:
    profile = _profile()
    # What the first sync leaves when LinkedIn brought no headline: never offered.
    profile.professions.insert(0, Profession(id="p-placeholder", text=PENDING_FIELD))

    state = _open(screen_data, profile)

    assert _listed(state) == [(FIRST_PROFESSION_ID, PROFESSION, ""), (ARCHITECT_ID, ARCHITECT, "")]
    assert state.profession_id == FIRST_PROFESSION_ID
    assert state.profession_in_language == PROFESSION
    assert state.pending == []

    # The session survives a reload; the next new CV still starts with the first one.
    run(WizardState.choose_profession, state, ARCHITECT_ID)
    run(WizardState.start, state)

    assert state.profession_id == FIRST_PROFESSION_ID


def test_the_dropdown_shows_the_cv_language_and_keeps_the_choice_on_switch(screen_data: Path) -> None:
    profile = _profile()
    profile.professions.append(Profession(id="p-cloud", text=CLOUD))
    state = _open(screen_data, profile)
    run(WizardState.choose_profession, state, ARCHITECT_ID)

    run(WizardState.change_language, state, "es")

    # With no Spanish yet the English stands in, marked as in the other lists.
    assert _listed(state) == [
        (FIRST_PROFESSION_ID, PROFESSION_ES, ""),
        (ARCHITECT_ID, ARCHITECT_ES, ""),
        ("p-cloud", CLOUD, "translation"),
    ]
    assert state.profession_id == ARCHITECT_ID
    assert state.profession_in_language == ARCHITECT_ES

    run(WizardState.change_language, state, "en")

    assert state.profession_id == ARCHITECT_ID
    assert state.profession_in_language == ARCHITECT


def test_choosing_a_profession_prints_it(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)

    run(WizardState.choose_profession, state, ARCHITECT_ID)

    content = state._current_content()
    assert isinstance(content, CVContent)
    assert content.personal.profession == ARCHITECT_ES
    selection = state._build_selection()
    assert (selection.profession_id, selection.header_profession) == (ARCHITECT_ID, None)


def test_choosing_a_profession_that_is_not_listed_is_ignored(screen_data: Path) -> None:
    profile = _profile()
    profile.professions.append(Profession(id="p-placeholder", text=PENDING_FIELD))
    state = _open(screen_data, profile)
    run(WizardState.choose_profession, state, ARCHITECT_ID)
    state.pdf_preview = "preview.pdf?v=1"

    run(WizardState.choose_profession, state, "p-placeholder")
    run(WizardState.choose_profession, state, "p-gone")

    assert state.profession_id == ARCHITECT_ID
    assert state.pdf_preview == "preview.pdf?v=1"


def test_choosing_a_profession_discards_the_preview(screen_data: Path) -> None:
    state = _open(screen_data)
    state.pdf_preview = "preview.pdf?v=1"

    run(WizardState.choose_profession, state, ARCHITECT_ID)

    assert state.pdf_preview == ""


# ------------------------------------------------------------------ cloning


def test_cloning_keeps_its_profession_by_id(screen_data: Path) -> None:
    # Edited after the CV was sent, it is still the same entry: the clone prints its new text.
    edited = edit_profession(_profile(), ARCHITECT_ID, "Lead Security Architect", "en")

    state = _clone(screen_data, Selection(profession_id=ARCHITECT_ID), made_in="en", now=edited)

    assert state.profession_id == ARCHITECT_ID
    assert state.profession_in_language == "Lead Security Architect"
    assert state.message == ""


@pytest.mark.parametrize(
    ("header", "made_in", "shown"),
    [(ARCHITECT, "es", ARCHITECT_ES), (ARCHITECT_ES, "en", ARCHITECT)],
    ids=["english-header-into-spanish", "spanish-header-into-english"],
)
def test_cloning_an_old_recipe_matches_the_header_in_either_language(
    screen_data: Path, header: str, made_in: str, shown: str
) -> None:
    """A recipe from before the list stored the headline as text, in the language it was made in."""
    state = _clone(screen_data, Selection(header_profession=header), made_in=made_in)

    assert state.language == made_in
    assert state.profession_id == ARCHITECT_ID
    assert state.profession_in_language == shown
    assert state.message == ""
    assert "Profession" not in state.pending_in_selection


def test_cloning_a_recipe_with_no_profession_takes_the_first_with_no_notice(screen_data: Path) -> None:
    state = _clone(screen_data, Selection())

    assert state.profession_id == FIRST_PROFESSION_ID
    assert state.message == ""


@pytest.mark.parametrize(
    "recipe",
    [Selection(profession_id=ARCHITECT_ID), Selection(header_profession="Ingeniera de seguridad")],
    ids=["entry-deleted", "old-header-that-matches-no-entry"],
)
def test_cloning_after_the_profession_was_deleted_says_so(screen_data: Path, recipe: Selection) -> None:
    now = remove_profession(_profile(), ARCHITECT_ID)

    state = _clone(screen_data, recipe, now=now)

    assert state.profession_id == FIRST_PROFESSION_ID
    assert state.profession_in_language == PROFESSION_ES
    assert state.message == GONE

    # The notice is about the clone, not the language: a switch keeps it.
    run(WizardState.change_language, state, "en")

    assert state.message == GONE


# ------------------------------------------------------------------ refreshing from disk


def test_refresh_list_keeps_the_choice_or_falls_back(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)
    run(WizardState.choose_profession, state, ARCHITECT_ID)
    state.pdf_preview = "preview.pdf?v=1"
    # Another tab adds a headline, with its Spanish.
    added = add_profession(_on_disk(screen_data), CLOUD, "en")
    cloud_id = added.professions[-1].id
    save_profile(screen_data, save_translation(added, "es", text_key(cloud_id, "text"), "Ingeniera de nube"))

    run(WizardState.update_professions, state)

    assert _listed(state) == [
        (FIRST_PROFESSION_ID, PROFESSION_ES, ""),
        (ARCHITECT_ID, ARCHITECT_ES, ""),
        (cloud_id, "Ingeniera de nube", ""),
    ]
    assert state.profession_id == ARCHITECT_ID
    assert state.pdf_preview == ""

    # Then it deletes the chosen one.
    save_profile(screen_data, remove_profession(_on_disk(screen_data), ARCHITECT_ID))

    run(WizardState.update_professions, state)

    assert [entry_id for entry_id, _, _ in _listed(state)] == [FIRST_PROFESSION_ID, cloud_id]
    assert state.profession_id == FIRST_PROFESSION_ID
    assert state.message == ""


def test_refresh_list_brings_the_first_profession_when_there_was_none(screen_data: Path) -> None:
    # What the first sync leaves when LinkedIn brought no headline.
    sample = bilingual.sample_profile()
    profile = sample.model_copy(
        update={
            "personal": sample.personal.model_copy(update={"profession": PENDING_FIELD}),
            "professions": [Profession(id=FIRST_PROFESSION_ID, text=PENDING_FIELD)],
        }
    )
    state = _open(screen_data, profile)
    assert (state.professions_list, state.profession_id, state.pending) == ([], "", ["profession"])

    save_profile(screen_data, edit_profession(_on_disk(screen_data), FIRST_PROFESSION_ID, CLOUD, "en"))
    run(WizardState.update_professions, state)

    assert state.profession_id == FIRST_PROFESSION_ID
    assert state.profession_in_language == CLOUD
    assert state.pending == []


# ------------------------------------------------------------------ the warning


def test_the_warning_lists_a_pending_profession(screen_data: Path) -> None:
    profile = _profile()
    profile.professions.append(Profession(id="p-cloud", text=CLOUD))
    save_content_language(screen_data, "es")
    state = _open(screen_data, profile)
    assert "Profession" not in state.pending_in_selection

    run(WizardState.choose_profession, state, "p-cloud")

    assert state.profession_pending
    assert state.pending_in_selection[0] == "Profession"

    # In English it is the source text: nothing pending.
    run(WizardState.change_language, state, "en")

    assert not state.profession_pending
    assert "Profession" not in state.pending_in_selection


# ------------------------------------------------------------------ the page


def test_step_two_offers_the_list_and_the_way_to_my_profile() -> None:
    rendered = str(application_step())

    assert "Profession under your name" not in rendered
    assert "professions_list" in rendered
    assert "choose_profession" in rendered
    assert "Add or edit in My profile" in rendered
    assert "/profile?section=contact" in rendered
    assert "update_professions" in rendered

"""The wizard builds the CV from the content in the CV's language, with My profile's marks.

The CV's language and the top-bar switch are the same value. The wizard opens in the
remembered language, a clone in its own, and changing it keeps every choice: only what
is shown is rebuilt. Before generating it says what among the checked items is pending in
that language, and never blocks.
"""

import errno
from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.app.config import DEFAULT_TEMPLATE
from cv_generator.app.pages.wizard import wizard_page
from cv_generator.app.states import wizard_state
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.models.cv import CVContent, GeneratedCV, SelectedExperience, Selection
from cv_generator.models.profile import Achievement, MasterProfile, ProfileText
from cv_generator.models.sections import SectionKind
from cv_generator.rendering.i18n import default_sections, load_language
from cv_generator.services.generation import save_cv
from cv_generator.services.preferences import load_content_language, save_content_language
from cv_generator.services.profile import SyncStatus, save_profile, save_sync_status
from cv_generator.services.translations import PROFESSION_KEY, save_translation, text_key
from tests import bilingual
from tests.screens import new_state, run

PROFESSION = "DevSecOps Engineer"
PROFESSION_ES = "Ingeniera DevSecOps"
PRESENTATION = "Security engineer who ships platforms."
OTHER_PRESENTATION = "Platform engineer focused on delivery."
CUT = "Cut deploy time by 40%"
CUT_ES = "Reduje el tiempo de despliegue en un 40%"
SCAN = "Automated scanning in 120 pipelines"
SCAN_ES = "Automatice el escaneo en 120 pipelines"
ROLE_ES = "Ingeniera de plataforma"
TITLE = "BSc in Computer Science"
TITLE_ES = "Licenciatura en Computacion"
DEGREE_ES = f"{TITLE_ES} · Universidad de Chile"


def _profile(*, edited_cut: bool = False) -> MasterProfile:
    """The shared sample with two presentation texts and two achievements, part of it in Spanish.

    In Spanish the profession, the presentation texts and the second achievement are
    missing; the job and the first achievement are translated, and the degree is pending
    review: its English changed after it was translated.
    """
    base = bilingual.sample_profile()
    job = base.experiences[0].model_copy(
        update={
            "achievements": [
                Achievement(id="ach-1", text=CUT, imported_value="Reduced deploy time" if edited_cut else CUT),
                Achievement(id="ach-2", text=SCAN, imported_value=SCAN),
            ]
        }
    )
    profile = base.model_copy(
        update={
            "profile_texts": [
                ProfileText(id="pt-1", text=PRESENTATION),
                ProfileText(id="pt-2", text=OTHER_PRESENTATION),
            ],
            "experiences": [job],
        }
    )
    for key, text in (
        (text_key("exp-1", "role"), ROLE_ES),
        (text_key("exp-1", "location"), "Santiago, Chile"),
        (text_key("ach-1", "text"), CUT_ES),
        (text_key("edu-1", "title"), TITLE_ES),
    ):
        profile = save_translation(profile, "es", key, text)
    return profile.model_copy(update={"education": [profile.education[0].model_copy(update={"title": TITLE})]})


def _open(data_dir: Path, profile: MasterProfile | None = None, address: str = "/new") -> WizardState:
    save_profile(data_dir, profile or _profile())
    state = new_state(WizardState, address)
    run(WizardState.start, state)
    return state


def _row(state: WizardState, key: str) -> dict[str, str]:
    return next(row for row in state.experience_rows if row["key"] == key)


def _cloned_cv(data_dir: Path, profile: MasterProfile) -> str:
    """A CV generated in Spanish with the second presentation text and the first achievement only."""
    selection = Selection(
        profile_text_id="pt-2",
        experiences=[SelectedExperience(id="exp-1", achievements=["ach-1"])],
    )
    cv = GeneratedCV(
        created=datetime(2026, 11, 2, 9, 0),  # noqa: DTZ001
        cv_name="Northwind",
        target_role="DevSecOps Engineer",
        language="es",
        template=DEFAULT_TEMPLATE,
        pdf_file=str(data_dir / "northwind.pdf"),
        selection=selection,
        content=CVContent(personal=profile.personal),
    )
    save_cv(data_dir, cv)
    return cv.cv_id


def _cannot_save(monkeypatch: pytest.MonkeyPatch) -> None:
    def full(data_dir: Path, language: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(wizard_state, "save_content_language", full)


# ------------------------------------------------------------------ opening


def test_the_wizard_opens_in_the_remembered_language(screen_data: Path) -> None:
    save_content_language(screen_data, "es")

    state = _open(screen_data)

    assert state.language == "es"
    assert _row(state, "exp-1|ach-1")["text"] == CUT_ES


def test_without_a_remembered_language_it_opens_in_the_source_one(screen_data: Path) -> None:
    """The language the last sync detected no longer decides it: the profile's source does."""
    save_sync_status(screen_data, SyncStatus(source="zip", timestamp=datetime(2026, 11, 1), detected_language="es"))  # noqa: DTZ001

    state = _open(screen_data)

    assert state.language == "en"
    assert _row(state, "exp-1|ach-1")["text"] == CUT


def test_a_clone_opens_in_its_language_and_remembers_it(screen_data: Path) -> None:
    profile = save_translation(_profile(), "es", PROFESSION_KEY, PROFESSION_ES)
    cv_id = _cloned_cv(screen_data, profile)
    save_content_language(screen_data, "en")

    state = _open(screen_data, profile, f"/new?from={cv_id}")

    assert state.language == "es"
    assert load_content_language(screen_data) == "es"
    assert _row(state, "exp-1|ach-1")["text"] == CUT_ES
    assert state.header_profession == PROFESSION_ES
    # The recipe kept no sections: the titles are the clone's language's, not the remembered one's.
    assert state.section_titles == {str(section.kind): section.title for section in default_sections("es")}
    assert state.profile_text_id == "pt-2"
    assert state.marked_achievements == {"exp-1|ach-1": True, "exp-1|ach-2": False}


def test_a_clone_whose_language_cannot_be_remembered_still_opens_in_it(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile()
    cv_id = _cloned_cv(screen_data, profile)
    _cannot_save(monkeypatch)

    state = _open(screen_data, profile, f"/new?from={cv_id}")

    assert state.language == "es"
    assert _row(state, "exp-1|ach-1")["text"] == CUT_ES
    assert state.message.startswith("The language could not be remembered: ")


# ------------------------------------------------------------------ changing it


def test_changing_language_keeps_the_choices(screen_data: Path) -> None:
    state = _open(screen_data)
    run(WizardState.choose_profile_text, state, "pt-2")
    run(WizardState.toggle_achievement, state, "exp-1|ach-2", False)
    run(WizardState.toggle, state, "skill-1", False)
    run(WizardState.change_title, state, "experience", "Where I worked")
    checks = (dict(state.marked_items), dict(state.marked_achievements))

    run(WizardState.change_language, state, "es")

    assert state.profile_text_id == "pt-2"
    assert (dict(state.marked_items), dict(state.marked_achievements)) == checks
    assert state.section_titles["experience"] == "Where I worked"
    assert state.section_titles["education"] == load_language("es").sections[SectionKind.EDUCATION]
    assert _row(state, "exp-1|ach-1")["text"] == CUT_ES
    assert CUT_ES in state.large_view
    assert load_content_language(screen_data) == "es"


def test_the_profile_profession_follows_the_language_and_yours_stays(screen_data: Path) -> None:
    state = _open(screen_data, save_translation(_profile(), "es", PROFESSION_KEY, PROFESSION_ES))
    assert state.header_profession == PROFESSION

    run(WizardState.change_language, state, "es")
    assert state.header_profession == PROFESSION_ES

    run(WizardState.update_header_profession, state, "AI Engineer")
    run(WizardState.change_language, state, "en")
    assert state.header_profession == "AI Engineer"


def test_choosing_the_language_already_on_does_not_discard_the_preview(screen_data: Path) -> None:
    state = _open(screen_data)
    state.pdf_preview = "preview.pdf?v=1"

    run(WizardState.change_language, state, "en")

    assert state.pdf_preview == "preview.pdf?v=1"
    assert load_content_language(screen_data) == "en"


def test_the_posting_is_compared_with_the_new_language_text(screen_data: Path) -> None:
    """A Spanish posting against the Spanish content, even from a step that does not show it."""
    state = _open(screen_data)
    run(WizardState.update_posting_text, state, "Buscamos experiencia en despliegue continuo y despliegue seguro.")
    run(WizardState.analyze_posting, state)
    assert [term["term"] for term in state.missing_terms] == ["despliegue"]

    run(WizardState.change_language, state, "es")

    assert [term["term"] for term in state.covered_terms] == ["despliegue"]
    assert state.missing_terms == []


def test_a_language_that_cannot_be_remembered_still_changes_and_says_so(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _open(screen_data)
    _cannot_save(monkeypatch)

    run(WizardState.change_language, state, "es")

    assert state.language == "es"
    assert _row(state, "exp-1|ach-1")["text"] == CUT_ES
    assert state.message.startswith("The language could not be remembered: ")


def test_an_unknown_language_is_ignored(screen_data: Path) -> None:
    state = _open(screen_data)

    run(WizardState.change_language, state, "xx")

    assert state.language == "en"
    assert load_content_language(screen_data) is None


# ------------------------------------------------------------------ lists and preview


def test_lists_show_the_spanish_with_marks(screen_data: Path) -> None:
    save_content_language(screen_data, "es")

    state = _open(screen_data)

    job = _row(state, "exp-1")
    assert (job["role"], job["pending"]) == (ROLE_ES, "")
    assert (_row(state, "exp-1|ach-1")["text"], _row(state, "exp-1|ach-1")["pending"]) == (CUT_ES, "")
    # No Spanish yet: the English stands in, marked.
    assert (_row(state, "exp-1|ach-2")["text"], _row(state, "exp-1|ach-2")["pending"]) == (SCAN, "translation")
    degree = next(row for row in state.other_rows if row["key"] == "edu-1")
    assert (degree["text"], degree["pending"]) == (DEGREE_ES, "review")
    assert [(text["text"], text["pending"]) for text in state.profile_texts_list] == [
        (PRESENTATION, "translation"),
        (OTHER_PRESENTATION, "translation"),
    ]
    # A skill name missing in Spanish is never pending, as in My profile.
    assert [(skill["name"], skill["pending"]) for skill in state.skills] == [("Kubernetes", "")]


def test_the_source_language_shows_no_marks(screen_data: Path) -> None:
    state = _open(screen_data)

    assert {row["pending"] for row in [*state.experience_rows, *state.other_rows, *state.profile_texts_list]} == {""}


def test_what_linkedin_said_is_shown_in_the_source_language_only(screen_data: Path) -> None:
    """LinkedIn said it in English: next to the Spanish text there is nothing to compare it with."""
    state = _open(screen_data, _profile(edited_cut=True))
    assert _row(state, "exp-1|ach-1")["origin"] == "Reduced deploy time"

    run(WizardState.change_language, state, "es")

    assert _row(state, "exp-1|ach-1")["origin"] == ""


def test_the_preview_content_is_in_the_cv_language(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)

    content = state._current_content()

    assert isinstance(content, CVContent)
    assert content.experiences[0].achievements[0].text == CUT_ES
    assert content.experiences[0].role == ROLE_ES


# ------------------------------------------------------------------ the warning


def test_the_warning_counts_only_checked_pending_items(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)

    # The second presentation text is pending too, but it is not the chosen one.
    assert state.pending_in_selection == ["Profession", PRESENTATION, SCAN, DEGREE_ES]
    assert state.pending_warning.startswith("4 checked items are pending in Spanish. ")

    # Unchecking the job takes its achievements out of the CV with it.
    run(WizardState.toggle, state, "exp-1", False)
    run(WizardState.toggle, state, "edu-1", False)
    # A profession written for this CV is not the profile's pending one.
    run(WizardState.update_header_profession, state, "Ingeniera de seguridad")

    assert state.pending_in_selection == [PRESENTATION]
    assert state.pending_warning == (
        "1 checked item is pending in Spanish. Where a text has no Spanish version the PDF uses the "
        "English one; where it is pending review, the Spanish text as it stands."
    )


def test_nothing_pending_says_nothing(screen_data: Path) -> None:
    state = _open(screen_data)

    assert state.pending_in_selection == []
    assert state.pending_warning == ""


# ------------------------------------------------------------------ refreshing from disk


def test_refreshing_the_achievements_brings_their_translations(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)
    save_profile(screen_data, save_translation(_profile(), "es", text_key("ach-2", "text"), SCAN_ES))

    run(WizardState.update_achievements, state)

    assert (_row(state, "exp-1|ach-2")["text"], _row(state, "exp-1|ach-2")["pending"]) == (SCAN_ES, "")
    assert SCAN not in state.pending_in_selection


def test_refreshing_the_skills_brings_their_translations(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)
    save_profile(screen_data, save_translation(_profile(), "es", text_key("skill-1", "name"), "Kubernetes (k8s)"))

    run(WizardState.update_skills, state)

    assert [skill["name"] for skill in state.skills] == ["Kubernetes (k8s)"]


def test_checking_the_contact_again_brings_the_profession_in_the_cv_language(screen_data: Path) -> None:
    save_content_language(screen_data, "es")
    state = _open(screen_data)
    assert state.header_profession == PROFESSION
    save_profile(screen_data, save_translation(_profile(), "es", PROFESSION_KEY, PROFESSION_ES))

    run(WizardState.fetch_contact_details, state)

    assert state.header_profession == PROFESSION_ES
    assert "Profession" not in state.pending_in_selection


# ------------------------------------------------------------------ the page


def test_the_page_has_the_switch_the_marks_and_the_warning() -> None:
    rendered = str(wizard_page())

    assert "content-language-es" in rendered
    assert "Pending translation" in rendered
    assert "Pending review" in rendered
    assert "pending_warning" in rendered

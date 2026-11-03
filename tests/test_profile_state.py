"""My profile in either language: Contact's profession, the skills and the menu counts.

The plain fields hold the source language (English here) and the Spanish lives in the
translations. What you type and do not save belongs to the language it was typed in.
"""

import errno
from pathlib import Path

import pytest

from cv_generator.app.states import profile_state
from cv_generator.app.states.profile_state import PROFILE_SECTIONS, ProfileState
from cv_generator.models.profile import MasterProfile, Skill, Translation
from cv_generator.services.preferences import load_content_language, save_content_language
from cv_generator.services.profile import PENDING_FIELD, load_profile, save_profile
from cv_generator.services.translations import PROFESSION_KEY, TextState, save_translation, state_in, text_key
from tests.bilingual import sample_profile
from tests.screens import new_state, run

ENGLISH_PROFESSION = "DevSecOps Engineer"
SPANISH_PROFESSION = "Ingeniera DevSecOps"
NAME_KEY = text_key("skill-1", "name")
CATEGORY_KEY = text_key("skill-1", "category")
LEVEL_KEY = text_key("skill-1", "level")


def _on_disk(data_dir: Path) -> MasterProfile:
    profile = load_profile(data_dir)
    assert profile is not None
    return profile


def _screen(data_dir: Path, profile: MasterProfile, language: str = "en") -> ProfileState:
    """My profile opened on this profile, in `language`. Nothing is remembered before."""
    save_profile(data_dir, profile)
    state = new_state(ProfileState)
    run(ProfileState.start, state)
    if state.language != language:
        run(ProfileState.switch_language, state, language)
    return state


def _profession_in_review() -> MasterProfile:
    """The Spanish profession was written against an English text that changed since."""
    stale = Translation(text=SPANISH_PROFESSION, source_text="Cloud Engineer")
    return sample_profile().model_copy(update={"translations": {"es": {PROFESSION_KEY: stale}}})


def _with_a_category() -> MasterProfile:
    """The sample skill with a category and no level, as a hand-written profile may have."""
    return sample_profile().model_copy(update={"skills": [Skill(id="skill-1", name="Kubernetes", category="Cloud")]})


# --------------------------------------------------------------------- Contact


def test_contact_in_spanish_saves_only_the_spanish_profession(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile(), "es")
    # Missing in Spanish: the field starts empty, with the English as the reference.
    assert state.profession == ""
    assert state.profession_state == "missing"
    assert state.profession_reference == ENGLISH_PROFESSION
    assert state.section_counts["contact"] == "2"
    assert not state.profession_required
    assert state.profession_copyable

    run(ProfileState.update, state, "profession", f" {SPANISH_PROFESSION} ")
    run(ProfileState.save, state)

    profile = _on_disk(screen_data)
    assert profile.personal.profession == ENGLISH_PROFESSION
    assert profile.translations["es"][PROFESSION_KEY].text == SPANISH_PROFESSION
    assert state.saved
    assert state.profession == SPANISH_PROFESSION
    assert state.profession_state == ""
    # The first entry of the list still has no Spanish: it goes away with the slot.
    assert state.section_counts["contact"] == "1"
    assert not state.has_unsaved_changes


def test_an_empty_spanish_profession_does_not_block_saving(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile(), "es")
    assert state.missing == []
    assert state.can_save

    run(ProfileState.update, state, "phone", "+56 9 3333 4444")
    run(ProfileState.save, state)

    profile = _on_disk(screen_data)
    assert state.saved
    assert profile.personal.phone == "+56 9 3333 4444"
    assert profile.personal.profession == ENGLISH_PROFESSION
    assert PROFESSION_KEY not in profile.translations.get("es", {})


def test_an_empty_english_profession_still_blocks_saving(screen_data: Path) -> None:
    """The source profession is the one the CV prints when the other language has none."""
    state = _screen(screen_data, sample_profile())

    run(ProfileState.update, state, "profession", "")

    assert state.missing == ["Profession"]
    assert not state.can_save


def test_a_placeholder_english_profession_makes_the_spanish_one_required(screen_data: Path) -> None:
    """The importer leaves 'PENDING' where LinkedIn brought no profession. Left empty, the
    Spanish CV would fall back to it, so the Spanish one is required and nothing is copied."""
    sample = sample_profile()
    pending = sample.model_copy(update={"personal": sample.personal.model_copy(update={"profession": PENDING_FIELD})})
    state = _screen(screen_data, pending, "es")

    assert state.profession_required
    assert state.missing == ["Profession"]
    assert not state.can_save
    assert not state.profession_copyable
    run(ProfileState.use_same_profession, state)
    assert state.profession == ""

    run(ProfileState.update, state, "profession", SPANISH_PROFESSION)
    run(ProfileState.save, state)

    profile = _on_disk(screen_data)
    assert state.saved
    assert profile.personal.profession == PENDING_FIELD
    assert profile.translations["es"][PROFESSION_KEY].text == SPANISH_PROFESSION


def test_typing_in_english_and_switching_never_saves_it_as_spanish(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile())
    run(ProfileState.update, state, "profession", "Platform Lead")

    run(ProfileState.switch_language, state, "es")
    assert state.profession == ""
    run(ProfileState.save, state)

    profile = _on_disk(screen_data)
    assert profile.personal.profession == ENGLISH_PROFESSION
    assert PROFESSION_KEY not in profile.translations.get("es", {})
    assert state.held_professions == {"en": "Platform Lead"}
    assert state.has_unsaved_changes
    assert state.unsaved_languages == "EN"

    run(ProfileState.switch_language, state, "en")

    assert state.profession == "Platform Lead"
    assert state.held_professions == {}
    assert state.has_unsaved_changes
    assert state.unsaved_languages == "EN"


def test_unsaved_changes_name_every_language_that_holds_them(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile())
    run(ProfileState.update, state, "profession", "Platform Lead")
    run(ProfileState.switch_language, state, "es")

    run(ProfileState.update, state, "profession", SPANISH_PROFESSION)

    assert state.unsaved_languages == "EN, ES"


def test_a_language_changed_in_another_tab_keeps_the_typing_in_its_own_language(screen_data: Path) -> None:
    """Opening a subsection reads the remembered language again, the way Home does."""
    state = _screen(screen_data, sample_profile())
    run(ProfileState.update, state, "profession", "Platform Lead")
    save_content_language(screen_data, "es")

    run(ProfileState.start, state)

    assert state.language == "es"
    assert state.profession == ""
    assert state.held_professions == {"en": "Platform Lead"}


def test_editing_the_english_profession_puts_the_spanish_in_review(screen_data: Path) -> None:
    translated = save_translation(sample_profile(), "es", PROFESSION_KEY, SPANISH_PROFESSION)
    state = _screen(screen_data, translated)

    run(ProfileState.update, state, "profession", "Security Engineer")
    run(ProfileState.save, state)

    assert state_in(_on_disk(screen_data), "es", PROFESSION_KEY) is TextState.REVIEW
    run(ProfileState.switch_language, state, "es")
    # The Spanish shows its own, older text, with the new English beside it.
    assert state.profession == SPANISH_PROFESSION
    assert state.profession_state == "review"
    assert state.profession_reference == "Security Engineer"


def test_still_good_and_same_text_on_the_profession(screen_data: Path) -> None:
    state = _screen(screen_data, _profession_in_review(), "es")
    assert state.profession_state == "review"

    run(ProfileState.confirm_profession, state)

    profile = _on_disk(screen_data)
    assert state_in(profile, "es", PROFESSION_KEY) is TextState.CURRENT
    assert profile.translations["es"][PROFESSION_KEY].text == SPANISH_PROFESSION
    assert state.profession_state == ""
    assert state.profession_reference == ""

    missing = _screen(screen_data, sample_profile(), "es")
    run(ProfileState.use_same_profession, missing)

    # It fills the field; Save writes it, like anything typed.
    assert missing.profession == ENGLISH_PROFESSION
    assert missing.has_unsaved_changes
    assert PROFESSION_KEY not in _on_disk(screen_data).translations.get("es", {})
    run(ProfileState.save, missing)
    assert _on_disk(screen_data).translations["es"][PROFESSION_KEY].text == ENGLISH_PROFESSION
    assert missing.profession_state == ""


def test_a_language_that_cannot_be_remembered_is_still_shown_and_the_failure_is_said(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _screen(screen_data, sample_profile())

    def full(data_dir: Path, language: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(profile_state, "save_content_language", full)
    run(ProfileState.switch_language, state, "es")

    assert state.language == "es"
    assert state.profession_state == "missing"
    assert state.language_error == "The language could not be remembered: the disk is full"


def test_a_switch_that_could_not_be_remembered_survives_opening_a_subsection(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A click in the menu runs `start` again. It keeps the language and the message
    instead of going back to the language still remembered on disk."""
    state = _screen(screen_data, sample_profile())

    def full(data_dir: Path, language: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(profile_state, "save_content_language", full)
    run(ProfileState.switch_language, state, "es")

    run(ProfileState.start, state)

    assert state.language == "es"
    assert state.profession_state == "missing"
    assert state.language_error == "The language could not be remembered: the disk is full"

    # Once a switch is remembered again, opening a subsection reads the file as before.
    monkeypatch.setattr(profile_state, "save_content_language", save_content_language)
    run(ProfileState.switch_language, state, "es")
    assert state.language_error == ""
    save_content_language(screen_data, "en")
    run(ProfileState.start, state)
    assert state.language == "en"


def test_an_unknown_language_is_ignored(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile())

    run(ProfileState.switch_language, state, "xx")

    assert state.language == "en"
    assert load_content_language(screen_data) is None


# ---------------------------------------------------------------------- Skills


def test_renaming_a_skill_in_spanish_writes_its_translation_only(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile(), "es")
    # A skill name missing in Spanish is the English one, with no mark.
    assert state.skills[0]["name"]["text"] == "Kubernetes"
    assert state.skills[0]["name"]["state"] == ""

    # Leaving the field with the name it showed writes nothing.
    run(ProfileState.rename_skill, state, "skill-1", "Kubernetes")
    assert NAME_KEY not in _on_disk(screen_data).translations.get("es", {})

    run(ProfileState.rename_from_form, state, {"id": "skill-1", "name": "Orquestación con Kubernetes"})

    profile = _on_disk(screen_data)
    assert profile.skills[0].name == "Kubernetes"
    assert profile.translations["es"][NAME_KEY].text == "Orquestación con Kubernetes"
    assert state.skills[0]["name"]["text"] == "Orquestación con Kubernetes"


def test_renaming_a_skill_in_english_puts_its_spanish_name_in_review(screen_data: Path) -> None:
    translated = save_translation(sample_profile(), "es", NAME_KEY, "Orquestación con Kubernetes")
    state = _screen(screen_data, translated)

    run(ProfileState.rename_skill, state, "skill-1", "K8s")

    profile = _on_disk(screen_data)
    assert profile.skills[0].name == "K8s"
    assert state_in(profile, "es", NAME_KEY) is TextState.REVIEW
    run(ProfileState.switch_language, state, "es")
    name = state.skills[0]["name"]
    assert (name["state"], name["reference"], name["copyable"]) == ("review", "K8s", "yes")
    assert state.section_counts["skills"] == "1"


def test_category_and_level_are_editable_only_in_spanish_and_only_when_english_has_them(
    screen_data: Path,
) -> None:
    state = _screen(screen_data, _with_a_category())
    assert state.skills[0]["category"]["text"] == "Cloud"
    assert state.skills[0]["category"]["editable"] == ""

    run(ProfileState.save_skill_field, state, CATEGORY_KEY, "Nube")
    assert _on_disk(screen_data).translations == {}

    run(ProfileState.switch_language, state, "es")
    category, level = state.skills[0]["category"], state.skills[0]["level"]
    assert (category["editable"], category["state"], category["own"], category["reference"]) == (
        "yes",
        "missing",
        "",
        "Cloud",
    )
    assert (level["editable"], level["text"]) == ("", "")

    run(ProfileState.save_skill_field, state, LEVEL_KEY, "Avanzado")
    run(ProfileState.skill_field_from_form, state, {"key": CATEGORY_KEY, "text": "Nube"})

    profile = _on_disk(screen_data)
    assert profile.skills[0].category == "Cloud"
    assert profile.translations["es"] == {CATEGORY_KEY: Translation(text="Nube", source_text="Cloud")}
    assert (state.skills[0]["category"]["own"], state.skills[0]["category"]["state"]) == ("Nube", "")


def test_still_good_and_same_text_on_a_skill_field(screen_data: Path) -> None:
    stale = Translation(text="Nube", source_text="Infrastructure")
    in_review = _with_a_category().model_copy(update={"translations": {"es": {CATEGORY_KEY: stale}}})
    state = _screen(screen_data, in_review, "es")
    assert state.skills[0]["category"]["state"] == "review"

    run(ProfileState.confirm_skill_field, state, CATEGORY_KEY)

    assert state_in(_on_disk(screen_data), "es", CATEGORY_KEY) is TextState.CURRENT
    assert state.skills[0]["category"]["state"] == ""

    missing = _screen(screen_data, _with_a_category(), "es")
    run(ProfileState.same_skill_field, missing, CATEGORY_KEY)

    assert _on_disk(screen_data).translations["es"][CATEGORY_KEY].text == "Cloud"
    assert missing.skills[0]["category"]["state"] == ""


# ------------------------------------------------------------------ Menu counts


def test_menu_counts_follow_the_language(screen_data: Path) -> None:
    state = _screen(screen_data, sample_profile())
    assert state.section_counts == dict.fromkeys(PROFILE_SECTIONS, "")

    run(ProfileState.switch_language, state, "es")

    # The profession twice (its slot and the first entry of the list, until the slot goes);
    # the role, location and achievement of the job; the study's title.
    # A missing skill name is not pending.
    assert state.section_counts == {
        **dict.fromkeys(PROFILE_SECTIONS, ""),
        "contact": "2",
        "experience": "3",
        "education": "1",
    }

    # Another subsection wrote on its own, and asks for the counts again.
    on_disk = _on_disk(screen_data)
    save_profile(screen_data, save_translation(on_disk, "es", text_key("ach-1", "text"), "Redujo el despliegue"))
    run(ProfileState.refresh_counts, state)

    assert state.section_counts["experience"] == "2"

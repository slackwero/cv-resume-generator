import pytest

from cv_generator.models.profile import MasterProfile, Translation
from cv_generator.services.translations import (
    PROFESSION_KEY,
    TextState,
    after_source_edit,
    confirm,
    copy_item,
    drop_item,
    field_states,
    in_language,
    item_marks,
    other_language,
    pending_by_section,
    pending_totals,
    save_translation,
    source_text_of,
    state_in,
    text_in,
)
from tests.bilingual import sample_profile

K = "ach-1.text"
EN_TEXT = "Cut deploy time by 40%"
ES_TEXT = "Redujo el tiempo de despliegue en un 40%"


def _sync_source(profile: MasterProfile, text: str) -> MasterProfile:
    """Changes the English the way a sync does: without telling the translation rules."""
    updated = profile.model_copy(deep=True)
    updated.experiences[0].achievements[0].text = text
    return updated


def _edit_source(profile: MasterProfile, text: str) -> MasterProfile:
    """Changes the English the way an editor does: and then calls the rule."""
    previous = source_text_of(profile, K)
    return after_source_edit(_sync_source(profile, text), K, previous)


def _with_spanish() -> MasterProfile:
    return save_translation(sample_profile(), "es", K, ES_TEXT)


def test_without_spanish_it_is_pending_translation_and_reads_in_english() -> None:
    p = sample_profile()

    assert state_in(p, "es", K) is TextState.MISSING
    assert text_in(p, "es", K) == EN_TEXT


def test_writing_the_spanish_makes_both_current() -> None:
    original = sample_profile()

    p = save_translation(original, "es", K, ES_TEXT)

    assert state_in(p, "es", K) is TextState.CURRENT
    assert state_in(p, "en", K) is TextState.CURRENT
    assert text_in(p, "es", K) == ES_TEXT
    assert original.translations == {}


def test_changing_the_english_puts_the_spanish_in_review() -> None:
    p = _edit_source(_with_spanish(), "Cut deploy time by half")

    assert state_in(p, "es", K) is TextState.REVIEW
    assert state_in(p, "en", K) is TextState.CURRENT
    assert text_in(p, "es", K) == ES_TEXT


def test_fixing_the_spanish_in_review_makes_both_current() -> None:
    p = _edit_source(_with_spanish(), "Cut deploy time by half")

    p = save_translation(p, "es", K, "Redujo el tiempo de despliegue a la mitad")

    assert state_in(p, "es", K) is TextState.CURRENT
    assert state_in(p, "en", K) is TextState.CURRENT


def test_changing_a_current_spanish_puts_the_english_in_review() -> None:
    p = save_translation(_with_spanish(), "es", K, "Redujo el despliegue en 40%")

    assert state_in(p, "en", K) is TextState.REVIEW
    assert state_in(p, "es", K) is TextState.CURRENT


def test_changing_the_spanish_again_keeps_the_first_agreed_text() -> None:
    p = save_translation(_with_spanish(), "es", K, "Uno")
    p = save_translation(p, "es", K, "Dos")

    assert p.translations["es"][K].agreed_text == ES_TEXT


def test_fixing_the_english_in_review_makes_both_current() -> None:
    p = save_translation(_with_spanish(), "es", K, "Redujo el despliegue en 40%")

    p = _edit_source(p, "Cut the deploy time by 40 percent")

    assert state_in(p, "en", K) is TextState.CURRENT
    assert state_in(p, "es", K) is TextState.CURRENT


def test_a_sync_over_an_english_in_review_leaves_the_spanish_in_review() -> None:
    p = save_translation(_with_spanish(), "es", K, "Redujo el despliegue en 40%")

    p = _sync_source(p, "Cut deploy time from 40 to 6 minutes")

    assert state_in(p, "en", K) is TextState.CURRENT
    assert state_in(p, "es", K) is TextState.REVIEW


def test_an_edit_of_a_current_english_changes_nothing_in_the_rules() -> None:
    p = _with_spanish()

    assert after_source_edit(p, K, EN_TEXT) == p


def test_still_good_clears_a_review_on_either_side() -> None:
    spanish_in_review = _edit_source(_with_spanish(), "Cut deploy time by half")
    english_in_review = save_translation(_with_spanish(), "es", K, "Redujo el despliegue en 40%")

    assert state_in(confirm(spanish_in_review, "es", K), "es", K) is TextState.CURRENT
    cleared = confirm(english_in_review, "en", K)
    assert state_in(cleared, "en", K) is TextState.CURRENT
    assert text_in(cleared, "es", K) == "Redujo el despliegue en 40%"


def test_there_is_nothing_to_confirm_without_a_translation() -> None:
    with pytest.raises(ValueError, match="nothing to confirm"):
        confirm(sample_profile(), "es", K)


def test_saving_the_same_spanish_again_changes_nothing() -> None:
    p = _with_spanish()

    assert save_translation(p, "es", K, ES_TEXT) == p


def test_an_empty_spanish_removes_the_translation() -> None:
    p = save_translation(_with_spanish(), "es", K, "   ")

    assert state_in(p, "es", K) is TextState.MISSING
    assert p.translations == {}


def test_the_source_language_is_not_saved_as_a_translation() -> None:
    with pytest.raises(ValueError):
        save_translation(sample_profile(), "en", K, "Anything")


def test_a_skill_name_without_spanish_is_not_pending() -> None:
    p = sample_profile()
    assert "skill-1.name" not in field_states(p, "es")

    p = save_translation(p, "es", "skill-1.name", "Kubernetes ES")
    p = p.model_copy(deep=True)
    p.skills[0].name = "K8s"

    assert field_states(p, "es")["skill-1.name"] is TextState.REVIEW


def test_an_optional_field_empty_in_english_has_nothing_to_translate() -> None:
    p = sample_profile().model_copy(deep=True)
    p.experiences[0].location = None

    assert "exp-1.location" not in field_states(p, "es")


def test_in_language_gives_a_plain_profile_with_fallbacks() -> None:
    p = _with_spanish()

    v = in_language(p, "es")

    assert v.experiences[0].achievements[0].text == ES_TEXT
    assert v.experiences[0].role == "Platform Engineer"
    assert v.translations == {}
    assert v.source_language == "es"
    assert in_language(v, "es") == v
    assert p.experiences[0].achievements[0].text == EN_TEXT


def test_in_language_keeps_an_empty_optional_field_empty() -> None:
    p = sample_profile().model_copy(deep=True)
    p.experiences[0].location = None

    assert in_language(p, "es").experiences[0].location is None


def test_an_achievement_written_only_in_spanish_reads_from_its_spanish_in_english() -> None:
    p = _sync_source(sample_profile(), "")
    p = save_translation(p, "es", K, ES_TEXT)

    assert in_language(p, "en").experiences[0].achievements[0].text == ES_TEXT
    assert state_in(p, "en", K) is TextState.MISSING


def test_keys_of_missing_items_or_unknown_fields_are_ignored() -> None:
    p = sample_profile().model_copy(deep=True)
    p.translations = {
        "es": {
            "gone-1.text": Translation(text="Fantasma", source_text="Ghost"),
            "ach-1.colour": Translation(text="Rojo", source_text="Red"),
        }
    }

    in_language(p, "es")
    assert "gone-1.text" not in field_states(p, "es")
    assert pending_totals(p, "es") == (5, 0)


def test_pending_totals_and_sections() -> None:
    p = sample_profile()

    assert pending_totals(p, "es") == (5, 0)
    assert pending_by_section(p, "es")["experience"] == 3
    assert pending_by_section(p, "es")["education"] == 1
    assert pending_by_section(p, "es")["contact"] == 1
    assert pending_by_section(p, "es")["skills"] == 0
    assert pending_totals(p, "en") == (0, 0)


def test_item_marks_say_missing_before_review() -> None:
    p = _edit_source(_with_spanish(), "Cut deploy time by half")

    marks = item_marks(p, "es")

    assert marks["exp-1"] is TextState.MISSING
    assert marks["personal"] is TextState.MISSING
    assert marks["ach-1"] is TextState.REVIEW
    assert PROFESSION_KEY == "personal.profession"


def test_copy_and_drop_item_follow_the_item() -> None:
    p = _with_spanish()

    copied = copy_item(p, "ach-1", "ach-2")
    assert copied.translations["es"]["ach-2.text"] == p.translations["es"][K]
    assert K in copied.translations["es"]

    dropped = drop_item(copied, "ach-1")
    assert K not in dropped.translations["es"]
    assert "ach-2.text" in dropped.translations["es"]
    assert drop_item(drop_item(dropped, "ach-2"), "ach-2").translations == {}


def test_the_other_language() -> None:
    assert other_language("en") == "es"
    assert other_language("es") == "en"

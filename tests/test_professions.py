"""Add, edit, copy, move and remove the profession headlines, in either language."""

import pytest

from cv_generator.models.profile import MasterProfile, Profession
from cv_generator.services.professions import (
    add_profession,
    copy_profession_text,
    edit_profession,
    move_profession,
    remove_profession,
    usable_professions,
    with_profession_mirror,
)
from cv_generator.services.profile import PENDING_FIELD
from cv_generator.services.translations import TextState, save_translation, state_in, text_in, text_key
from tests.bilingual import sample_profile

FIRST = "profession-headline"


def _key(profession_id: str) -> str:
    return text_key(profession_id, "text")


def _two() -> MasterProfile:
    profile = sample_profile()
    profile.professions.append(Profession(id="p-2", text="Security Architect"))
    profile.professions.append(Profession(id="p-3", text="Cloud Engineer"))
    return profile


def test_adding_in_spanish_leaves_the_english_pending() -> None:
    result = add_profession(sample_profile(), "Ingeniera DevSecOps", "es")

    added = result.professions[-1]
    assert added.text == ""
    assert state_in(result, "en", _key(added.id)) is TextState.MISSING
    assert text_in(result, "es", _key(added.id)) == "Ingeniera DevSecOps"
    assert text_in(result, "en", _key(added.id)) == "Ingeniera DevSecOps"


def test_adding_in_the_source_language_appends_the_text() -> None:
    result = add_profession(sample_profile(), "  Cloud Engineer ", "en")

    assert [p.text for p in result.professions] == ["DevSecOps Engineer", "Cloud Engineer"]


def test_an_empty_profession_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        add_profession(sample_profile(), "  ", "en")
    with pytest.raises(ValueError, match="cannot be empty"):
        edit_profession(sample_profile(), FIRST, "", "es")


def test_editing_the_english_puts_the_spanish_in_review() -> None:
    profile = save_translation(sample_profile(), "es", _key(FIRST), "Ingeniero DevSecOps")

    result = edit_profession(profile, FIRST, "Lead DevSecOps Engineer", "en")

    assert result.professions[0].text == "Lead DevSecOps Engineer"
    assert state_in(result, "es", _key(FIRST)) is TextState.REVIEW
    assert result.personal.profession == "Lead DevSecOps Engineer"


def test_editing_the_spanish_saves_a_translation_and_keeps_the_source() -> None:
    result = edit_profession(sample_profile(), FIRST, "Ingeniero DevSecOps", "es")

    assert result.professions[0].text == "DevSecOps Engineer"
    assert text_in(result, "es", _key(FIRST)) == "Ingeniero DevSecOps"


def test_editing_an_unknown_profession_is_refused() -> None:
    with pytest.raises(ValueError, match="no longer exists"):
        edit_profession(sample_profile(), "nope", "x", "en")


def test_use_the_same_text_copies_the_spanish_into_a_missing_english() -> None:
    profile = add_profession(sample_profile(), "Ingeniera DevSecOps", "es")
    added = profile.professions[-1].id

    result = copy_profession_text(profile, added, "en")

    assert result.professions[-1].text == "Ingeniera DevSecOps"
    assert state_in(result, "en", _key(added)) is TextState.CURRENT
    assert state_in(result, "es", _key(added)) is TextState.CURRENT


def test_use_the_same_text_copies_the_english_into_a_missing_spanish() -> None:
    result = copy_profession_text(sample_profile(), FIRST, "es")

    assert text_in(result, "es", _key(FIRST)) == "DevSecOps Engineer"
    assert state_in(result, "es", _key(FIRST)) is TextState.CURRENT


def test_use_the_same_text_is_refused_on_a_version_in_review() -> None:
    profile = save_translation(sample_profile(), "es", _key(FIRST), "Ingeniero DevSecOps")
    profile = edit_profession(profile, FIRST, "Lead DevSecOps Engineer", "en")

    with pytest.raises(ValueError):
        copy_profession_text(profile, FIRST, "es")


def test_use_the_same_text_is_refused_on_a_current_version() -> None:
    with pytest.raises(ValueError):
        copy_profession_text(sample_profile(), FIRST, "en")


def test_the_last_profession_cannot_be_deleted() -> None:
    with pytest.raises(ValueError, match="keep at least one"):
        remove_profession(sample_profile(), FIRST)


def test_deleting_drops_its_translations() -> None:
    profile = save_translation(_two(), "es", _key("p-2"), "Arquitecto de seguridad")

    result = remove_profession(profile, "p-2")

    assert [p.id for p in result.professions] == [FIRST, "p-3"]
    assert _key("p-2") not in result.translations.get("es", {})


def test_the_mirror_follows_the_first_usable_entry() -> None:
    profile = _two()
    profile.professions[0].text = PENDING_FIELD

    assert [p.id for p in usable_professions(profile)] == ["p-2", "p-3"]
    assert with_profession_mirror(profile).personal.profession == "Security Architect"


def test_the_mirror_is_pending_without_a_usable_entry() -> None:
    profile = sample_profile()
    profile.professions[0].text = PENDING_FIELD

    assert usable_professions(profile) == []
    assert with_profession_mirror(profile).personal.profession == PENDING_FIELD


def test_an_entry_written_only_in_spanish_is_usable_and_mirrors_that_text() -> None:
    profile = sample_profile()
    profile.professions[0].text = PENDING_FIELD
    profile = add_profession(profile, "Ingeniera DevSecOps", "es")

    assert [p.id for p in usable_professions(profile)] == [profile.professions[-1].id]
    assert profile.personal.profession == "Ingeniera DevSecOps"


def test_moving_reorders_and_the_mirror_follows() -> None:
    result = move_profession(_two(), "p-2", -1)

    assert [p.id for p in result.professions] == ["p-2", FIRST, "p-3"]
    assert result.personal.profession == "Security Architect"


def test_moving_stops_at_the_ends() -> None:
    result = move_profession(_two(), "p-3", 5)
    assert [p.id for p in result.professions] == [FIRST, "p-2", "p-3"]
    result = move_profession(result, FIRST, -5)
    assert [p.id for p in result.professions] == [FIRST, "p-2", "p-3"]


def test_operations_do_not_change_the_profile_they_receive() -> None:
    profile = _two()
    before = profile.model_dump()

    move_profession(profile, "p-3", -2)
    remove_profession(profile, "p-2")
    add_profession(profile, "X", "es")

    assert profile.model_dump() == before

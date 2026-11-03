"""Presentation, Education, Courses and Languages: read-only in the source language,
translated by hand in the other one."""

import asyncio
import errno
from pathlib import Path

import pytest

from cv_generator.app.states import translation_state
from cv_generator.app.states.profile_state import ProfileState
from cv_generator.app.states.translation_state import TranslationState, text_rows
from cv_generator.models.profile import Course, Language, MasterProfile, ProfileText
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import save_translation, text_key
from tests import bilingual
from tests.screens import new_state, run

PRESENTATION_KEY = text_key("pt-1", "text")
TITLE_KEY = text_key("edu-1", "title")
COURSE_KEY = text_key("course-1", "name")
LEVEL_KEY = text_key("lang-1", "level")
LANGUAGE_KEY = text_key("lang-1", "language")


def _profile() -> MasterProfile:
    return bilingual.sample_profile().model_copy(
        update={
            "profile_texts": [ProfileText(id="pt-1", text="Security engineer with ten years of experience.")],
            "courses": [Course(id="course-1", name="Cloud Security", institution="SANS", year=2021)],
            "languages": [Language(id="lang-1", language="English", level=None)],
        }
    )


def _screen(tab: TranslationState) -> ProfileState:
    return asyncio.run(tab.get_state(ProfileState))


def _open(data_dir: Path, profile: MasterProfile | None = None, language: str = "en") -> TranslationState:
    save_profile(data_dir, profile or _profile())
    tab = new_state(TranslationState, "/profile?section=education")
    run(ProfileState.start, _screen(tab))
    run(TranslationState.start, tab)
    if tab.language != language:
        run(ProfileState.switch_language, _screen(tab), language)
        run(TranslationState.show_language, tab)
    return tab


def _row(tab: TranslationState, section: str, key: str) -> dict[str, str]:
    return next(row for row in tab.rows[section] if row["key"] == key)


def _stored(data_dir: Path, key: str) -> str | None:
    profile = load_profile(data_dir)
    assert profile is not None
    entry = profile.translations.get("es", {}).get(key)
    return entry.text if entry else None


def test_rows_in_english_are_read_only(screen_data: Path) -> None:
    tab = _open(screen_data)
    rows = [row for section in tab.rows.values() for row in section]
    assert rows
    assert all(row["editable"] == "" for row in rows)
    assert _row(tab, "education", TITLE_KEY)["text"] == "BSc Computer Science"
    assert _row(tab, "education", TITLE_KEY)["context"] == "Universidad de Chile"
    assert _row(tab, "courses", COURSE_KEY)["context"] == "SANS · 2021"

    run(TranslationState.save_text, tab, TITLE_KEY, "Licenciatura")
    assert tab.error == "The English text comes from LinkedIn and is changed there."
    assert _stored(screen_data, TITLE_KEY) is None


def test_a_study_title_saved_in_spanish_is_its_translation(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    assert _row(tab, "education", TITLE_KEY)["editable"] == "yes"

    events = run(TranslationState.save_text, tab, TITLE_KEY, "Licenciatura en Ciencias de la Computación")

    assert events == [ProfileState.refresh_counts]
    assert _stored(screen_data, TITLE_KEY) == "Licenciatura en Ciencias de la Computación"
    profile = load_profile(screen_data)
    assert profile is not None
    assert profile.education[0].title == "BSc Computer Science"
    assert _row(tab, "education", TITLE_KEY)["own"] == "Licenciatura en Ciencias de la Computación"


def test_the_form_saves_the_same_way(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    run(TranslationState.save_from_form, tab, {"key": PRESENTATION_KEY, "text": "Ingeniera de seguridad."})
    assert _stored(screen_data, PRESENTATION_KEY) == "Ingeniera de seguridad."


def test_the_same_blur_twice_writes_once(screen_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tab = _open(screen_data, language="es")
    saves: list[MasterProfile] = []

    def spy(data_dir: Path, profile: MasterProfile) -> None:
        saves.append(profile)
        save_profile(data_dir, profile)

    monkeypatch.setattr(translation_state, "save_profile", spy)

    run(TranslationState.save_text, tab, COURSE_KEY, "Seguridad en la nube")
    run(TranslationState.save_text, tab, COURSE_KEY, "Seguridad en la nube")

    assert len(saves) == 1


def test_same_text_copies_the_english(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    assert _row(tab, "courses", COURSE_KEY)["copyable"] == "yes"

    run(TranslationState.same_text, tab, COURSE_KEY)

    assert _stored(screen_data, COURSE_KEY) == "Cloud Security"
    assert _row(tab, "courses", COURSE_KEY)["state"] == ""


def test_still_good_clears_a_review(screen_data: Path) -> None:
    profile = save_translation(_profile(), "es", COURSE_KEY, "Seguridad en la nube")
    changed = profile.model_copy(update={"courses": [profile.courses[0].model_copy(update={"name": "Cloud Defense"})]})
    tab = _open(screen_data, changed, "es")
    assert _row(tab, "courses", COURSE_KEY)["state"] == "review"

    run(TranslationState.confirm, tab, COURSE_KEY)

    assert _row(tab, "courses", COURSE_KEY)["state"] == ""
    assert _stored(screen_data, COURSE_KEY) == "Seguridad en la nube"


def test_a_field_empty_in_english_offers_no_input(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    level = _row(tab, "languages", LEVEL_KEY)
    assert level["editable"] == ""
    assert _row(tab, "languages", LANGUAGE_KEY)["editable"] == "yes"

    run(TranslationState.save_text, tab, LEVEL_KEY, "Nativo")
    assert _stored(screen_data, LEVEL_KEY) is None


def test_an_unknown_key_is_ignored(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    assert run(TranslationState.save_text, tab, "nope.text", "x") is None
    assert tab.error == ""


def test_the_other_language_follows_the_switch(screen_data: Path) -> None:
    tab = _open(screen_data)
    run(ProfileState.switch_language, _screen(tab), "es")
    run(TranslationState.show_language, tab)
    assert tab.language == "es"
    assert _row(tab, "education", TITLE_KEY)["state"] == "missing"


def test_rows_of_a_profile_without_items_are_empty() -> None:
    assert text_rows(bilingual.sample_profile(), "en", "presentation") == []


def _count_saves(monkeypatch: pytest.MonkeyPatch) -> list[MasterProfile]:
    saves: list[MasterProfile] = []

    def spy(data_dir: Path, profile: MasterProfile) -> None:
        saves.append(profile)
        save_profile(data_dir, profile)

    monkeypatch.setattr(translation_state, "save_profile", spy)
    return saves


def test_no_profile_on_disk_shows_nothing_and_no_error(screen_data: Path) -> None:
    tab = new_state(TranslationState, "/profile?section=education")
    run(ProfileState.start, _screen(tab))
    run(TranslationState.start, tab)
    assert tab.error == ""
    assert all(rows == [] for rows in tab.rows.values())


def test_an_unreadable_profile_is_an_error_not_a_crash(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    (screen_data / "profile.json").write_text("{ not json", encoding="utf-8")

    run(TranslationState.start, tab)

    assert tab.error.startswith("Your profile could not be read: ")
    assert all(rows == [] for rows in tab.rows.values())
    # ProfileState.switch_language reads the same file; this is only the follower.
    _screen(tab).language = "en"
    run(TranslationState.show_language, tab)
    assert tab.error.startswith("Your profile could not be read: ")


def test_a_failed_save_shows_the_error_and_what_is_on_disk(screen_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tab = _open(screen_data, language="es")

    def full(data_dir: Path, profile: MasterProfile) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(translation_state, "save_profile", full)
    run(TranslationState.save_text, tab, COURSE_KEY, "Seguridad")

    assert tab.error == "Nothing was saved: the disk is full."
    assert tab.error_at == COURSE_KEY
    assert _row(tab, "courses", COURSE_KEY)["own"] == ""
    assert _stored(screen_data, COURSE_KEY) is None


def test_confirm_in_english_and_same_text_on_a_non_copyable_row_write_nothing(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saves = _count_saves(monkeypatch)
    english = _open(screen_data)
    run(TranslationState.confirm, english, COURSE_KEY)
    assert saves == []

    spanish = _open(screen_data, language="es")
    run(TranslationState.same_text, spanish, LEVEL_KEY)
    assert saves == []


def test_an_edit_against_an_unreadable_profile_keeps_the_rows(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")
    (screen_data / "profile.json").write_text("{ not json", encoding="utf-8")

    run(TranslationState.save_text, tab, COURSE_KEY, "Seguridad en la nube")

    assert [row["key"] for row in tab.rows["courses"]] == ["course-1.name"]
    assert tab.error != ""
    # The row is still on screen, so that is where the error shows.
    assert tab.error_at == COURSE_KEY


def test_an_edit_of_a_row_deleted_in_another_tab_shows_the_error_above_the_list(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab = _open(screen_data, language="es")
    save_profile(screen_data, _profile().model_copy(update={"courses": []}))

    def full(data_dir: Path, profile: MasterProfile) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(translation_state, "save_profile", full)
    run(TranslationState.save_text, tab, COURSE_KEY, "Seguridad en la nube")

    assert tab.error == "Nothing was saved: the disk is full."
    # The row is gone from the refreshed list, so the error shows above it.
    assert tab.error_at == ""
    assert tab.rows["courses"] == []

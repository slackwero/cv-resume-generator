"""Contact's list of professions: add, edit, move and delete, in either language."""

import asyncio
import errno
from pathlib import Path

import pytest

from cv_generator.app.states import profession_state
from cv_generator.app.states.profession_state import ProfessionState
from cv_generator.app.states.profile_state import ProfileState
from cv_generator.models.profile import MasterProfile, Profession, Translation
from cv_generator.services.placeholders import PENDING_FIELD
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import text_key
from tests.bilingual import sample_profile
from tests.screens import new_state, run

FIRST = "profession-headline"
FIRST_KEY = text_key(FIRST, "text")
SECOND_KEY = text_key("p-2", "text")


def _profile() -> MasterProfile:
    """Two headlines; the second one already has its Spanish."""
    profile = sample_profile()
    profile.professions.append(Profession(id="p-2", text="Security Architect"))
    profile.translations = {
        "es": {SECOND_KEY: Translation(text="Arquitecta de seguridad", source_text="Security Architect")}
    }
    return profile


def _screen(tab: ProfessionState) -> ProfileState:
    return asyncio.run(tab.get_state(ProfileState))


def _open(data_dir: Path, profile: MasterProfile | None = None, language: str = "en") -> ProfessionState:
    save_profile(data_dir, profile or _profile())
    return _reopen(data_dir, language)


def _reopen(data_dir: Path, language: str = "en") -> ProfessionState:
    """The screen on the profile already on disk, as another tab would open it."""
    tab = new_state(ProfessionState, "/profile?section=contact")
    run(ProfileState.start, _screen(tab))
    run(ProfessionState.start, tab)
    if tab.language != language:
        run(ProfileState.switch_language, _screen(tab), language)
        run(ProfessionState.show_language, tab)
    return tab


def _on_disk(data_dir: Path) -> MasterProfile:
    profile = load_profile(data_dir)
    assert profile is not None
    return profile


def _row(tab: ProfessionState, key: str) -> dict[str, str]:
    return next(row for row in tab.rows if row["key"] == key)


def test_rows_show_the_list_in_the_switch_language_with_marks(screen_data: Path) -> None:
    english = _open(screen_data)
    assert [row["text"] for row in english.rows] == ["DevSecOps Engineer", "Security Architect"]
    assert [(row["first"], row["last"]) for row in english.rows] == [("yes", ""), ("", "yes")]
    assert all(row["editable"] == "yes" and row["label"] == "Profession" for row in english.rows)
    assert all(row["state"] == "" for row in english.rows)

    spanish = _open(screen_data, language="es")
    first, second = spanish.rows
    # Missing: the English stands in, marked, and "Use the same text" is offered.
    assert (first["text"], first["own"], first["state"], first["copyable"]) == (
        "DevSecOps Engineer",
        "",
        "missing",
        "yes",
    )
    assert first["reference"] == "DevSecOps Engineer"
    assert (second["text"], second["own"], second["state"], second["copyable"]) == (
        "Arquitecta de seguridad",
        "Arquitecta de seguridad",
        "",
        "",
    )


def test_adding_editing_and_moving_save_right_away(screen_data: Path) -> None:
    tab = _open(screen_data)

    events = run(ProfessionState.add, tab, {"text": " Cloud Engineer "})
    assert events == [ProfileState.refresh_counts]
    added = _on_disk(screen_data).professions[-1]
    assert added.text == "Cloud Engineer"
    assert [row["text"] for row in tab.rows][-1] == "Cloud Engineer"

    key = text_key(added.id, "text")
    run(ProfessionState.save, tab, key, "Cloud Security Engineer")
    assert _on_disk(screen_data).professions[-1].text == "Cloud Security Engineer"

    run(ProfessionState.save_from_form, tab, {"key": FIRST_KEY, "text": "Lead DevSecOps Engineer"})
    disk = _on_disk(screen_data)
    assert disk.professions[0].text == "Lead DevSecOps Engineer"
    assert disk.personal.profession == "Lead DevSecOps Engineer"

    # Editing the English puts the existing Spanish in review.
    run(ProfessionState.save, tab, "p-2.text", "Security Lead")
    assert _row(tab, SECOND_KEY)["text"] == "Security Lead"

    run(ProfessionState.move, tab, key, -1)
    disk = _on_disk(screen_data)
    assert [p.id for p in disk.professions] == [FIRST, added.id, "p-2"]
    assert [row["key"] for row in tab.rows] == [FIRST_KEY, key, SECOND_KEY]
    run(ProfessionState.move, tab, key, -1)
    run(ProfessionState.move, tab, key, 1)
    run(ProfessionState.move, tab, key, 2)  # not a step of the buttons: ignored
    assert [p.id for p in _on_disk(screen_data).professions] == [FIRST, added.id, "p-2"]


def test_an_unchanged_or_unknown_save_writes_nothing(screen_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tab = _open(screen_data)
    saves: list[int] = []
    monkeypatch.setattr(profession_state, "save_profile", lambda *args: saves.append(1))

    assert run(ProfessionState.save, tab, FIRST_KEY, " DevSecOps Engineer ") is None
    assert run(ProfessionState.save, tab, "nope.text", "x") is None
    assert saves == []

    run(ProfessionState.save, tab, FIRST_KEY, "")
    assert tab.error == "The profession cannot be empty."
    assert tab.error_at == FIRST_KEY


def test_adding_in_spanish_creates_a_pending_translation_in_english(screen_data: Path) -> None:
    tab = _open(screen_data, language="es")

    run(ProfessionState.add, tab, {"text": "Ingeniera de nube"})

    added = _on_disk(screen_data).professions[-1]
    assert added.text == ""
    row = _row(tab, text_key(added.id, "text"))
    assert (row["text"], row["state"]) == ("Ingeniera de nube", "")
    english = _reopen(screen_data)
    assert (_row(english, row["key"])["state"], _row(english, row["key"])["text"]) == ("missing", "Ingeniera de nube")

    run(ProfessionState.add, tab, {"text": "  "})
    assert tab.error == "The profession cannot be empty."
    assert tab.error_at == "add"


def test_use_the_same_text_works_from_either_language(screen_data: Path) -> None:
    spanish = _open(screen_data, language="es")
    events = run(ProfessionState.same, spanish, FIRST_KEY)
    assert events == [ProfileState.refresh_counts]
    assert _on_disk(screen_data).translations["es"][FIRST_KEY].text == "DevSecOps Engineer"
    assert _row(spanish, FIRST_KEY)["state"] == ""
    # Not offered where nothing is missing: nothing is written.
    assert run(ProfessionState.same, spanish, SECOND_KEY) is None

    # An entry written only in Spanish: its English is the missing one.
    run(ProfessionState.add, spanish, {"text": "Ingeniera de nube"})
    added = text_key(_on_disk(screen_data).professions[-1].id, "text")
    english = _reopen(screen_data)
    assert _row(english, added)["copyable"] == "yes"
    run(ProfessionState.same, english, added)
    assert _on_disk(screen_data).professions[-1].text == "Ingeniera de nube"
    assert _row(english, added)["state"] == ""


def test_a_placeholder_is_not_a_text_to_copy_or_edit_from(screen_data: Path) -> None:
    profile = sample_profile()
    profile.professions = [Profession(id=FIRST, text=PENDING_FIELD)]
    profile.personal = profile.personal.model_copy(update={"profession": PENDING_FIELD})

    spanish = _open(screen_data, profile, "es")

    row = _row(spanish, FIRST_KEY)
    assert (row["own"], row["copyable"]) == ("", "")
    english = _open(screen_data, profile)
    assert _row(english, FIRST_KEY)["own"] == ""
    assert _row(english, FIRST_KEY)["text"] == ""


def test_still_good_clears_a_review(screen_data: Path) -> None:
    profile = _profile()
    profile.translations = {
        "es": {SECOND_KEY: Translation(text="Arquitecta de seguridad", source_text="Cloud Architect")}
    }
    tab = _open(screen_data, profile, "es")
    assert _row(tab, SECOND_KEY)["state"] == "review"

    events = run(ProfessionState.confirm, tab, SECOND_KEY)

    assert events == [ProfileState.refresh_counts]
    assert _row(tab, SECOND_KEY)["state"] == ""
    assert run(ProfessionState.confirm, tab, SECOND_KEY) is None


def test_deleting_asks_first_and_the_last_one_is_refused(screen_data: Path) -> None:
    tab = _open(screen_data)

    run(ProfessionState.confirm_delete, tab, "p-2.text")  # nobody asked
    assert len(_on_disk(screen_data).professions) == 2

    run(ProfessionState.ask_delete, tab, "p-2.text")
    assert tab.confirming_key == "p-2.text"
    run(ProfessionState.cancel_delete, tab)
    assert tab.confirming_key == ""
    assert len(_on_disk(screen_data).professions) == 2

    run(ProfessionState.ask_delete, tab, "p-2.text")
    run(ProfessionState.confirm_delete, tab, "p-2.text")
    disk = _on_disk(screen_data)
    assert [p.id for p in disk.professions] == [FIRST]
    assert SECOND_KEY not in disk.translations.get("es", {})
    assert tab.confirming_key == ""

    # The only one left cannot be asked about, and the service refuses it anyway.
    run(ProfessionState.ask_delete, tab, FIRST_KEY)
    assert tab.confirming_key == ""
    tab.confirming_key = FIRST_KEY
    run(ProfessionState.confirm_delete, tab, FIRST_KEY)
    assert tab.error == "A CV needs a profession: keep at least one."
    assert tab.error_at == FIRST_KEY
    assert [p.id for p in _on_disk(screen_data).professions] == [FIRST]


def test_a_failed_save_shows_the_error_and_what_is_on_disk(screen_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tab = _open(screen_data)

    def full(data_dir: Path, profile: MasterProfile) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(profession_state, "save_profile", full)
    run(ProfessionState.save, tab, FIRST_KEY, "Lead")

    assert tab.error == "Nothing was saved: the disk is full."
    assert tab.error_at == FIRST_KEY
    assert _row(tab, FIRST_KEY)["own"] == "DevSecOps Engineer"


def test_a_failed_switch_keeps_the_list_in_the_chosen_language(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The R8/R12 pattern: the choice could not be remembered, so the file still holds the
    other language, and the list follows the screen and not the file."""
    from cv_generator.app.states import profile_state

    tab = _open(screen_data)

    def full(data_dir: Path, language: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(profile_state, "save_content_language", full)
    run(ProfileState.switch_language, _screen(tab), "es")
    run(ProfessionState.show_language, tab)
    assert tab.language == "es"
    assert _row(tab, FIRST_KEY)["state"] == "missing"

    # Opening the screen again (a click in the menu) keeps it in Spanish too.
    run(ProfileState.start, _screen(tab))
    run(ProfessionState.start, tab)
    assert tab.language == "es"
    assert _row(tab, FIRST_KEY)["state"] == "missing"


def test_an_unreadable_profile_is_an_error_not_a_crash(screen_data: Path) -> None:
    tab = _open(screen_data)
    (screen_data / "profile.json").write_text("{ not json", encoding="utf-8")

    run(ProfessionState.start, tab)

    assert tab.error.startswith("Your profile could not be read: ")
    assert tab.rows == []


def test_no_profile_on_disk_shows_nothing_and_no_error(screen_data: Path) -> None:
    tab = new_state(ProfessionState, "/profile?section=contact")
    run(ProfileState.start, _screen(tab))
    run(ProfessionState.start, tab)
    assert tab.error == ""
    assert tab.rows == []

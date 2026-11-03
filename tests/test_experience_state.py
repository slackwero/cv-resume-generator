"""What the Work experience editor does when you click: drafts, errors, guards and focus.

It also works in either language: the plain fields hold the source language (English
here) and the Spanish lives in the translations.
"""

import asyncio
import errno
from pathlib import Path

import pytest

from cv_generator.app.states import experience_state, profile_state
from cv_generator.app.states.experience_state import (
    ExperienceRow,
    ExperienceState,
    achievement_rows,
    focus_after_delete,
    focus_after_move,
)
from cv_generator.app.states.profile_state import ProfileState
from cv_generator.models.profile import Experience, MasterProfile, Translation
from cv_generator.services.achievements import remove_achievement
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import save_translation, text_key
from tests import bilingual
from tests.screens import new_state, run
from tests.test_experience_rows import sample_profile

SCAN = "exp-acme|achievement-scan"
TRIAGE = "exp-acme|achievement-triage"
LLM = "exp-acme|achievement-llm"
ADD_NORTH = "exp-north|add"

# The bilingual sample: one job with one achievement, nothing in Spanish yet.
ACHIEVEMENT = "exp-1|ach-1"
ACHIEVEMENT_KEY = text_key("ach-1", "text")
ROLE_KEY = text_key("exp-1", "role")
LOCATION_KEY = text_key("exp-1", "location")
ENGLISH = "Cut deploy time by 40%"
SPANISH = "Reduje el tiempo de despliegue un 40%"


def _profile_screen(editor: ExperienceState) -> ProfileState:
    """The rest of My profile, in the same tab as the editor."""
    return asyncio.run(editor.get_state(ProfileState))


def _switch(editor: ExperienceState, code: str) -> None:
    """One click on the switch, as the page wires it: My profile switches, then the editor follows."""
    run(ProfileState.switch_language, _profile_screen(editor), code)
    run(ExperienceState.show_language, editor)


def _open(data_dir: Path, profile: MasterProfile, language: str = "en") -> ExperienceState:
    """Work experience opened on this profile, the way the page's on_load runs, in `language`."""
    save_profile(data_dir, profile)
    editor = new_state(ExperienceState, "/profile?section=experience")
    run(ProfileState.start, _profile_screen(editor))
    run(ExperienceState.start, editor)
    if editor.language != language:
        _switch(editor, language)
    return editor


@pytest.fixture
def editor(screen_data: Path) -> ExperienceState:
    return _open(screen_data, sample_profile())


def _texts(data_dir: Path) -> list[str]:
    profile = load_profile(data_dir)
    assert profile is not None
    return [achievement.text for achievement in profile.experiences[0].achievements]


# --- folding --------------------------------------------------------------------


def test_the_first_job_opens_and_the_rest_fold(editor: ExperienceState) -> None:
    assert editor.open_jobs == {"exp-acme": True, "exp-north": False}


def test_opening_the_screen_again_keeps_what_you_folded(editor: ExperienceState) -> None:
    """Back from another subsection runs `start` again, and it is not a new visit."""
    run(ExperienceState.toggle_job, editor, "exp-acme")
    run(ExperienceState.toggle_job, editor, "exp-north")

    run(ExperienceState.start, editor)

    assert editor.open_jobs == {"exp-acme": False, "exp-north": True}


def test_a_job_that_appeared_on_disk_comes_in_folded(editor: ExperienceState, screen_data: Path) -> None:
    profile = sample_profile()
    profile.experiences.append(Experience(id="exp-new", company="Initech", role="SRE", start="2017-01"))
    save_profile(screen_data, profile)

    run(ExperienceState.duplicate, editor, SCAN)

    assert editor.open_jobs["exp-new"] is False


# --- drafts ---------------------------------------------------------------------


def test_leaving_the_editor_for_another_achievement_keeps_what_you_typed(editor: ExperienceState) -> None:
    run(ExperienceState.start_edit, editor, SCAN)
    run(ExperienceState.keep_draft, editor, SCAN, "Scanned 200 pipelines.")
    run(ExperienceState.start_edit, editor, TRIAGE)

    assert editor.editing_key == TRIAGE
    assert editor.drafts == {SCAN: "Scanned 200 pipelines."}


def test_folding_the_job_keeps_the_form_and_what_you_typed(editor: ExperienceState) -> None:
    """Unfolding shows the form again, opened with the draft."""
    run(ExperienceState.start_add, editor, "exp-north")
    run(ExperienceState.keep_draft, editor, ADD_NORTH, "Moved the pipelines to GitHub Actions.")
    run(ExperienceState.toggle_job, editor, "exp-north")

    assert editor.adding_to == "exp-north"
    assert editor.drafts == {ADD_NORTH: "Moved the pipelines to GitHub Actions."}


@pytest.mark.parametrize(
    ("key", "text"),
    [
        (SCAN, "Automated scanning in 120 pipelines."),
        # Saving trims it, and a textarea turns CRLF into LF: no change either.
        (SCAN, "Automated scanning in 120 pipelines.  "),
        (ADD_NORTH, "   "),
    ],
    ids=["the saved text again", "the saved text and a space", "an empty new one"],
)
def test_a_draft_that_changes_nothing_is_not_kept(editor: ExperienceState, key: str, text: str) -> None:
    editor.editing_key, editor.adding_to = SCAN, ""
    if key == ADD_NORTH:
        editor.editing_key, editor.adding_to = "", "exp-north"
    editor.drafts = {key: "Something typed before."}

    run(ExperienceState.keep_draft, editor, key, text)

    assert editor.drafts == {}


def test_a_draft_that_arrives_after_its_form_closed_is_ignored(editor: ExperienceState) -> None:
    """What is typed also travels a moment after the last key, and may land after Cancel or Save."""
    run(ExperienceState.start_edit, editor, SCAN)
    run(ExperienceState.cancel_edit, editor)

    run(ExperienceState.keep_draft, editor, SCAN, "Scanned 200 pipelines.")

    assert editor.drafts == {}


def test_a_draft_for_a_row_not_on_screen_is_ignored(editor: ExperienceState) -> None:
    run(ExperienceState.keep_draft, editor, "exp-acme|achievement-gone", "Text.")
    run(ExperienceState.keep_draft, editor, "exp-acme", "A job heading is not a form.")

    assert editor.drafts == {}


def test_cancel_discards_the_draft(editor: ExperienceState) -> None:
    run(ExperienceState.start_edit, editor, SCAN)
    run(ExperienceState.keep_draft, editor, SCAN, "Scanned 200 pipelines.")
    run(ExperienceState.cancel_edit, editor)

    run(ExperienceState.start_add, editor, "exp-north")
    run(ExperienceState.keep_draft, editor, ADD_NORTH, "Moved the pipelines.")
    run(ExperienceState.cancel_add, editor)

    assert editor.drafts == {}


def test_saving_clears_the_draft(editor: ExperienceState, screen_data: Path) -> None:
    run(ExperienceState.start_edit, editor, SCAN)
    run(ExperienceState.keep_draft, editor, SCAN, "Scanned 200 pipelines.")
    run(ExperienceState.save_edit, editor, {"text": "Scanned 200 pipelines."})

    assert editor.drafts == {}
    assert editor.editing_key == ""
    assert _texts(screen_data)[0] == "Scanned 200 pipelines."


def test_a_rejected_save_keeps_the_editor_and_the_draft(editor: ExperienceState) -> None:
    run(ExperienceState.start_edit, editor, SCAN)
    run(ExperienceState.keep_draft, editor, SCAN, "  ")
    run(ExperienceState.save_edit, editor, {"text": "  "})

    assert editor.editing_key == SCAN
    assert editor.drafts == {SCAN: "  "}
    assert editor.error == "The achievement cannot be empty."
    assert editor.error_at == SCAN


def test_the_draft_of_an_achievement_deleted_elsewhere_is_dropped(editor: ExperienceState, screen_data: Path) -> None:
    """In every language: the one held for the language not on screen goes too."""
    editor.drafts = {SCAN: "Scanned 200 pipelines."}
    editor.held_drafts = {"es": {SCAN: "Escaneé 200 pipelines.", TRIAGE: "Hice un servicio de triaje."}}
    save_profile(screen_data, remove_achievement(sample_profile(), "exp-acme", "achievement-scan"))

    run(ExperienceState.start, editor)

    assert editor.drafts == {}
    assert editor.held_drafts == {"es": {TRIAGE: "Hice un servicio de triaje."}}


# --- where an error shows -------------------------------------------------------


def test_a_failed_move_shows_its_error_under_its_row(editor: ExperienceState, monkeypatch: pytest.MonkeyPatch) -> None:
    def full_disk(*_: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device", "/Users/someone/cv-generator/data/.profile.json.tmp")

    monkeypatch.setattr(experience_state, "save_profile", full_disk)

    run(ExperienceState.move, editor, TRIAGE, 1)

    assert editor.error == "Nothing was saved: the disk is full."
    assert editor.error_at == TRIAGE


def test_an_error_about_a_row_that_is_gone_shows_above_the_list(editor: ExperienceState, screen_data: Path) -> None:
    save_profile(screen_data, remove_achievement(sample_profile(), "exp-acme", "achievement-scan"))

    run(ExperienceState.duplicate, editor, SCAN)

    assert editor.error == "That achievement no longer exists in your profile. Reload the page."
    assert editor.error_at == ""
    # And the list no longer offers the row that fails.
    assert SCAN not in {row["key"] for row in editor.rows}


def test_starting_another_action_clears_the_error(editor: ExperienceState) -> None:
    editor.error, editor.error_at = "Something failed.", TRIAGE

    run(ExperienceState.start_edit, editor, SCAN)

    assert (editor.error, editor.error_at) == ("", "")


# --- guards ---------------------------------------------------------------------


def test_only_the_achievement_asked_about_is_deleted(editor: ExperienceState, screen_data: Path) -> None:
    run(ExperienceState.ask_delete, editor, SCAN)
    run(ExperienceState.confirm_delete, editor, TRIAGE)

    assert len(_texts(screen_data)) == 3

    focus = run(ExperienceState.confirm_delete, editor, SCAN)

    assert len(_texts(screen_data)) == 2
    assert editor.confirming_key == ""
    assert f"edit-{TRIAGE}" in str(focus)


def test_a_second_click_on_save_does_nothing(editor: ExperienceState, screen_data: Path) -> None:
    run(ExperienceState.start_edit, editor, SCAN)
    run(ExperienceState.save_edit, editor, {"text": "First."})
    run(ExperienceState.save_edit, editor, {"text": "Second."})

    assert _texts(screen_data)[0] == "First."


def test_a_move_of_more_than_one_step_is_ignored(editor: ExperienceState, screen_data: Path) -> None:
    run(ExperienceState.move, editor, SCAN, 2)

    assert _texts(screen_data)[0] == "Automated scanning in 120 pipelines."


# --- focus ----------------------------------------------------------------------


def _rows() -> list[ExperienceRow]:
    return achievement_rows(sample_profile(), "en")


@pytest.mark.parametrize(
    ("key", "target"),
    [(SCAN, f"edit-{TRIAGE}"), (TRIAGE, f"edit-{LLM}"), (LLM, f"edit-{TRIAGE}")],
    ids=["the first", "a middle one", "the last"],
)
def test_after_a_delete_the_keyboard_goes_to_the_achievement_in_its_place(key: str, target: str) -> None:
    assert focus_after_delete(_rows(), key) == target


def test_after_deleting_the_only_achievement_the_keyboard_goes_to_add() -> None:
    profile = sample_profile()
    for achievement_id in ("achievement-scan", "achievement-triage"):
        profile = remove_achievement(profile, "exp-acme", achievement_id)

    assert focus_after_delete(achievement_rows(profile, "en"), LLM) == "add-exp-acme"


@pytest.mark.parametrize(
    ("key", "offset", "target"),
    [
        (TRIAGE, 1, f"move-down-{TRIAGE}"),
        (TRIAGE, -1, f"move-up-{TRIAGE}"),
        # Reached the end: that arrow is disabled now, so the keyboard goes to the other one.
        (LLM, 1, f"move-up-{LLM}"),
        (SCAN, -1, f"move-down-{SCAN}"),
    ],
)
def test_after_a_move_the_keyboard_stays_on_the_arrow(key: str, offset: int, target: str) -> None:
    assert focus_after_move(_rows(), key, offset) == target


def test_closing_a_form_puts_the_keyboard_back_on_its_button(editor: ExperienceState) -> None:
    run(ExperienceState.start_edit, editor, SCAN)
    assert f"edit-{SCAN}" in str(run(ExperienceState.cancel_edit, editor))

    run(ExperienceState.ask_delete, editor, SCAN)
    assert f"delete-{SCAN}" in str(run(ExperienceState.cancel_delete, editor))

    run(ExperienceState.start_add, editor, "exp-north")
    assert "add-exp-north" in str(run(ExperienceState.cancel_add, editor))


# --- either language ------------------------------------------------------------


def _on_disk(data_dir: Path) -> MasterProfile:
    profile = load_profile(data_dir)
    assert profile is not None
    return profile


def _row(editor: ExperienceState, key: str) -> ExperienceRow:
    return next(row for row in editor.rows if row["key"] == key)


def _achievements(editor: ExperienceState) -> list[ExperienceRow]:
    return [row for row in editor.rows if row["row"] == "achievement"]


def test_editing_a_missing_spanish_starts_empty_with_the_english_as_reference(screen_data: Path) -> None:
    editor = _open(screen_data, bilingual.sample_profile(), "es")

    run(ExperienceState.start_edit, editor, ACHIEVEMENT)

    row = _row(editor, ACHIEVEMENT)
    assert editor.editing_key == ACHIEVEMENT
    assert (row["own"], row["state"], row["reference"]) == ("", "missing", ENGLISH)
    # A draft is told apart from the Spanish text, empty, and not from the English shown.
    run(ExperienceState.keep_draft, editor, ACHIEVEMENT, "  ")
    assert editor.drafts == {}
    run(ExperienceState.keep_draft, editor, ACHIEVEMENT, ENGLISH)
    assert editor.drafts == {ACHIEVEMENT: ENGLISH}


def test_a_draft_typed_in_english_stays_in_english_after_switching(screen_data: Path) -> None:
    editor = _open(screen_data, bilingual.sample_profile())
    run(ExperienceState.start_edit, editor, ACHIEVEMENT)
    run(ExperienceState.keep_draft, editor, ACHIEVEMENT, "Cut deploy time by half")

    _switch(editor, "es")

    assert editor.language == "es"
    assert editor.editing_key == ""
    assert editor.drafts == {}
    assert editor.held_drafts == {"en": {ACHIEVEMENT: "Cut deploy time by half"}}
    # And the row says so from Spanish, naming the language by its code like Contact.
    assert editor.held_draft_languages == {ACHIEVEMENT: "EN"}

    run(ExperienceState.start_edit, editor, ACHIEVEMENT)
    run(ExperienceState.keep_draft, editor, ACHIEVEMENT, "Reduje el despliegue a la mitad")
    _switch(editor, "en")

    assert editor.drafts == {ACHIEVEMENT: "Cut deploy time by half"}
    assert editor.held_drafts == {"es": {ACHIEVEMENT: "Reduje el despliegue a la mitad"}}
    assert editor.held_draft_languages == {ACHIEVEMENT: "ES"}
    # Switching saves neither of them.
    profile = _on_disk(screen_data)
    assert profile.experiences[0].achievements[0].text == ENGLISH
    assert profile.translations == {}


def test_saving_in_spanish_writes_the_translation_and_leaves_the_english_text(screen_data: Path) -> None:
    editor = _open(screen_data, bilingual.sample_profile(), "es")
    screen = _profile_screen(editor)
    assert screen.section_counts["experience"] == "3"

    run(ExperienceState.start_edit, editor, ACHIEVEMENT)
    events = run(ExperienceState.save_edit, editor, {"text": f" {SPANISH} "})

    profile = _on_disk(screen_data)
    assert profile.experiences[0].achievements[0].text == ENGLISH
    assert profile.translations["es"][ACHIEVEMENT_KEY].text == SPANISH
    row = _row(editor, ACHIEVEMENT)
    assert (row["text"], row["own"], row["state"]) == (SPANISH, SPANISH, "")
    assert editor.editing_key == ""
    # The menu counts follow every write.
    assert isinstance(events, list)
    assert ProfileState.refresh_counts in events
    assert f"edit-{ACHIEVEMENT}" in str(events)
    run(ProfileState.refresh_counts, screen)
    assert screen.section_counts["experience"] == "2"


def test_an_empty_spanish_achievement_is_rejected(screen_data: Path) -> None:
    editor = _open(screen_data, bilingual.sample_profile(), "es")
    run(ExperienceState.start_edit, editor, ACHIEVEMENT)

    run(ExperienceState.save_edit, editor, {"text": "  "})

    assert editor.error == "The achievement cannot be empty."
    assert editor.editing_key == ACHIEVEMENT
    assert _on_disk(screen_data).translations == {}


def test_adding_in_spanish_shows_the_spanish_marked_pending_in_english(screen_data: Path) -> None:
    editor = _open(screen_data, bilingual.sample_profile(), "es")
    run(ExperienceState.start_add, editor, "exp-1")

    events = run(ExperienceState.add, editor, {"text": "Automaticé los escaneos"})

    assert ProfileState.refresh_counts in events
    added = _achievements(editor)[-1]
    assert (added["text"], added["state"]) == ("Automaticé los escaneos", "")
    assert _on_disk(screen_data).experiences[0].achievements[-1].text == ""

    _switch(editor, "en")

    added = _achievements(editor)[-1]
    assert (added["text"], added["own"], added["state"], added["reference"]) == (
        "Automaticé los escaneos",
        "",
        "missing",
        "Automaticé los escaneos",
    )


def test_duplicate_and_delete_carry_both_languages(screen_data: Path) -> None:
    profile = save_translation(bilingual.sample_profile(), "es", ACHIEVEMENT_KEY, SPANISH)
    editor = _open(screen_data, profile, "es")

    assert ProfileState.refresh_counts in run(ExperienceState.duplicate, editor, ACHIEVEMENT)

    original, copy = _achievements(editor)
    assert [(row["text"], row["state"]) for row in (original, copy)] == [(SPANISH, ""), (SPANISH, "")]

    run(ExperienceState.ask_delete, editor, ACHIEVEMENT)
    assert ProfileState.refresh_counts in run(ExperienceState.confirm_delete, editor, ACHIEVEMENT)

    assert [row["key"] for row in _achievements(editor)] == [copy["key"]]
    spanish = _on_disk(screen_data).translations["es"]
    assert ACHIEVEMENT_KEY not in spanish
    assert spanish[text_key(copy["achievement_id"], "text")].text == SPANISH


def test_role_and_location_are_editable_only_in_the_other_language(screen_data: Path) -> None:
    editor = _open(screen_data, bilingual.sample_profile())

    run(ExperienceState.save_job_field, editor, ROLE_KEY, "Ingeniera de plataforma")

    assert editor.error == "The English text comes from LinkedIn and is changed there."
    assert editor.error_at == "exp-1"
    assert _on_disk(screen_data).translations == {}

    _switch(editor, "es")
    assert editor.error == ""
    events = run(ExperienceState.save_job_field, editor, ROLE_KEY, " Ingeniera de plataforma ")
    run(ExperienceState.job_field_from_form, editor, {"key": LOCATION_KEY, "text": "Santiago de Chile"})

    assert ProfileState.refresh_counts in events
    profile = _on_disk(screen_data)
    assert (profile.experiences[0].role, profile.experiences[0].location) == ("Platform Engineer", "Santiago, Chile")
    assert profile.translations["es"][ROLE_KEY].text == "Ingeniera de plataforma"
    assert profile.translations["es"][LOCATION_KEY].text == "Santiago de Chile"
    job = _row(editor, "exp-1")
    assert (job["role"]["text"], job["role"]["state"]) == ("Ingeniera de plataforma", "")
    assert (job["location"]["text"], job["location"]["state"]) == ("Santiago de Chile", "")


def test_a_job_text_on_blur_after_enter_writes_nothing_again(screen_data: Path) -> None:
    """Enter and leaving the field both send it: the second one finds it saved."""
    editor = _open(screen_data, bilingual.sample_profile(), "es")
    run(ExperienceState.job_field_from_form, editor, {"key": ROLE_KEY, "text": "Ingeniera de plataforma"})

    assert run(ExperienceState.save_job_field, editor, ROLE_KEY, "Ingeniera de plataforma") is None


def test_still_good_and_same_text_on_the_role_and_location(screen_data: Path) -> None:
    stale = Translation(text="Ingeniera Cloud", source_text="Cloud Engineer")
    profile = bilingual.sample_profile().model_copy(update={"translations": {"es": {ROLE_KEY: stale}}})
    editor = _open(screen_data, profile, "es")
    job = _row(editor, "exp-1")
    assert (job["role"]["state"], job["role"]["reference"]) == ("review", "Platform Engineer")

    assert ProfileState.refresh_counts in run(ExperienceState.confirm_job_field, editor, ROLE_KEY)
    assert ProfileState.refresh_counts in run(ExperienceState.same_job_field, editor, LOCATION_KEY)

    spanish = _on_disk(screen_data).translations["es"]
    assert (spanish[ROLE_KEY].text, spanish[ROLE_KEY].source_text) == ("Ingeniera Cloud", "Platform Engineer")
    assert spanish[LOCATION_KEY].text == "Santiago, Chile"
    job = _row(editor, "exp-1")
    assert (job["role"]["state"], job["location"]["state"]) == ("", "")


def test_still_good_on_an_achievement_in_review(screen_data: Path) -> None:
    stale = Translation(text=SPANISH, source_text="Cut deploy time by 30%")
    profile = bilingual.sample_profile().model_copy(update={"translations": {"es": {ACHIEVEMENT_KEY: stale}}})
    editor = _open(screen_data, profile, "es")
    row = _row(editor, ACHIEVEMENT)
    assert (row["text"], row["state"], row["reference"]) == (SPANISH, "review", ENGLISH)

    events = run(ExperienceState.confirm, editor, ACHIEVEMENT)

    assert ProfileState.refresh_counts in events
    entry = _on_disk(screen_data).translations["es"][ACHIEVEMENT_KEY]
    assert (entry.text, entry.source_text) == (SPANISH, ENGLISH)
    assert _row(editor, ACHIEVEMENT)["state"] == ""
    # Only a version in review is confirmed: a current one has nothing to agree on.
    assert run(ExperienceState.confirm, editor, ACHIEVEMENT) is None


def test_restoring_the_linkedin_text_is_only_offered_in_english(editor: ExperienceState, screen_data: Path) -> None:
    assert editor.in_source
    _switch(editor, "es")
    assert not editor.in_source

    run(ExperienceState.start_edit, editor, TRIAGE)
    run(ExperienceState.restore, editor, TRIAGE)

    assert _texts(screen_data)[1] == "Built a FastAPI triage service."


def test_a_failed_switch_and_a_menu_click_keep_the_work_experience_in_spanish(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The editor shows the language My profile shows, even one the file could not remember."""
    editor = _open(screen_data, bilingual.sample_profile())

    def full(data_dir: Path, language: str) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(profile_state, "save_content_language", full)
    _switch(editor, "es")

    # A click in the menu runs the page's on_load again, in its order.
    run(ProfileState.start, _profile_screen(editor))
    run(ExperienceState.start, editor)

    assert editor.language == "es"
    assert _row(editor, ACHIEVEMENT)["state"] == "missing"

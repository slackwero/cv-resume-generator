"""What the Work experience editor does when you click: drafts, errors, guards and focus."""

from pathlib import Path

import pytest

from cv_generator.app.states import experience_state
from cv_generator.app.states.experience_state import (
    ExperienceState,
    achievement_rows,
    focus_after_delete,
    focus_after_move,
)
from cv_generator.models.profile import Experience
from cv_generator.services.achievements import remove_achievement
from cv_generator.services.profile import load_profile, save_profile
from tests.screens import new_state, run
from tests.test_experience_rows import sample_profile

SCAN = "exp-acme|achievement-scan"
TRIAGE = "exp-acme|achievement-triage"
LLM = "exp-acme|achievement-llm"
ADD_NORTH = "exp-north|add"


@pytest.fixture
def editor(screen_data: Path) -> ExperienceState:
    save_profile(screen_data, sample_profile())
    state = new_state(ExperienceState)
    run(ExperienceState.start, state)
    return state


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
    editor.drafts = {SCAN: "Scanned 200 pipelines."}
    save_profile(screen_data, remove_achievement(sample_profile(), "exp-acme", "achievement-scan"))

    run(ExperienceState.start, editor)

    assert editor.drafts == {}


# --- where an error shows -------------------------------------------------------


def test_a_failed_move_shows_its_error_under_its_row(editor: ExperienceState, monkeypatch: pytest.MonkeyPatch) -> None:
    def full_disk(*_: object) -> None:
        raise OSError("No space left on device")

    monkeypatch.setattr(experience_state, "save_profile", full_disk)

    run(ExperienceState.move, editor, TRIAGE, 1)

    assert editor.error == "No space left on device"
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


def _rows() -> list[dict[str, str]]:
    return achievement_rows(sample_profile())


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

    assert focus_after_delete(achievement_rows(profile), LLM) == "add-exp-acme"


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

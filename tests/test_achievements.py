"""Edit, duplicate, add, remove and reorder the achievements of a job by hand.

What the owner does by hand has to survive the next sync: that is tested in test_merge.py.
"""

import pytest

from cv_generator.models.profile import Achievement, Experience, MasterProfile
from cv_generator.services.achievements import (
    AchievementOrigin,
    add_achievement,
    duplicate_achievement,
    edit_achievement,
    move_achievement,
    origin_of,
    remove_achievement,
    restore_linkedin_text,
)
from tests.test_models_personal import REQUIRED


@pytest.fixture
def profile() -> MasterProfile:
    return MasterProfile(
        personal=REQUIRED,
        experiences=[
            Experience(
                id="exp-acme",
                company="Acme Cloud",
                role="DevSecOps Engineer",
                start="2022-03",
                current=True,
                achievements=[
                    Achievement(
                        id="achievement-scan",
                        text="Automated scanning in 120 pipelines.",
                        imported_value="Automated scanning in 120 pipelines.",
                    ),
                    Achievement(
                        id="achievement-triage",
                        text="Built a FastAPI triage service.",
                        imported_value="Improved the triage of findings.",
                    ),
                    Achievement(id="achievement-llm", text="Developed an LLM assistant for SAST fixes."),
                ],
            )
        ],
    )


def _ids(profile: MasterProfile) -> list[str]:
    return [achievement.id for achievement in profile.experiences[0].achievements]


def _copy_of(profile: MasterProfile, original_id: str) -> Achievement:
    return next(a for a in profile.experiences[0].achievements if a.copy_of == original_id)


def test_origin_tells_linkedin_edited_and_yours_apart(profile: MasterProfile) -> None:
    scan, triage, llm = profile.experiences[0].achievements

    assert origin_of(scan) is AchievementOrigin.LINKEDIN
    assert origin_of(triage) is AchievementOrigin.EDITED
    assert origin_of(llm) is AchievementOrigin.YOURS


# ------------------------------------------------------------------ add


def test_add_appends_one_of_yours_at_the_end(profile: MasterProfile) -> None:
    result = add_achievement(profile, "exp-acme", "  Designed a RAG pipeline over runbooks.  ")

    added = result.experiences[0].achievements[-1]
    assert added.text == "Designed a RAG pipeline over runbooks."
    assert added.imported_value is None and added.copy_of is None
    assert _ids(result)[:3] == ["achievement-scan", "achievement-triage", "achievement-llm"]


@pytest.mark.parametrize("text", ["", "   "])
def test_add_and_edit_reject_an_empty_text(profile: MasterProfile, text: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        add_achievement(profile, "exp-acme", text)
    with pytest.raises(ValueError, match="cannot be empty"):
        edit_achievement(profile, "exp-acme", "achievement-scan", text)


# ----------------------------------------------------------------- edit


def test_edit_keeps_the_id_and_the_linkedin_origin(profile: MasterProfile) -> None:
    result = edit_achievement(profile, "exp-acme", "achievement-scan", "Wrote the scanning templates in Python.")

    edited = result.experiences[0].achievements[0]
    assert (edited.id, edited.text, edited.imported_value) == (
        "achievement-scan",
        "Wrote the scanning templates in Python.",
        "Automated scanning in 120 pipelines.",
    )
    assert origin_of(edited) is AchievementOrigin.EDITED


def test_editing_back_to_the_linkedin_text_is_linkedin_again(profile: MasterProfile) -> None:
    result = edit_achievement(profile, "exp-acme", "achievement-triage", "  Improved the triage of findings. ")

    assert origin_of(result.experiences[0].achievements[1]) is AchievementOrigin.LINKEDIN


def test_restore_puts_back_the_linkedin_text(profile: MasterProfile) -> None:
    result = restore_linkedin_text(profile, "exp-acme", "achievement-triage")

    assert result.experiences[0].achievements[1].text == "Improved the triage of findings."


def test_restore_rejects_one_of_yours(profile: MasterProfile) -> None:
    with pytest.raises(ValueError, match="did not come from LinkedIn"):
        restore_linkedin_text(profile, "exp-acme", "achievement-llm")


# ------------------------------------------------------------ duplicate


def test_duplicate_inserts_the_copy_right_below_its_original(profile: MasterProfile) -> None:
    result = duplicate_achievement(profile, "exp-acme", "achievement-scan")

    copy = _copy_of(result, "achievement-scan")
    assert _ids(result) == ["achievement-scan", copy.id, "achievement-triage", "achievement-llm"]
    assert copy.text == "Automated scanning in 120 pipelines."
    assert copy.imported_value is None
    assert copy.id != "achievement-scan"


# --------------------------------------------------------------- remove


def test_removing_a_linkedin_one_remembers_its_linkedin_text(profile: MasterProfile) -> None:
    result = remove_achievement(profile, "exp-acme", "achievement-triage")

    assert result.experiences[0].dismissed_achievements == ["Improved the triage of findings."]
    assert "achievement-triage" not in _ids(result)


def test_removing_one_of_yours_dismisses_nothing(profile: MasterProfile) -> None:
    result = remove_achievement(profile, "exp-acme", "achievement-llm")

    assert result.experiences[0].dismissed_achievements == []
    assert "achievement-llm" not in _ids(result)


def test_removing_twice_the_same_linkedin_text_stores_it_once(profile: MasterProfile) -> None:
    profile.experiences[0].achievements.append(
        Achievement(
            id="achievement-scan-again",
            text="Another wording.",
            imported_value="Automated scanning in 120 pipelines.",
        )
    )

    result = remove_achievement(profile, "exp-acme", "achievement-scan")
    result = remove_achievement(result, "exp-acme", "achievement-scan-again")

    assert result.experiences[0].dismissed_achievements == ["Automated scanning in 120 pipelines."]


def test_removing_a_copy_in_the_middle_points_its_copies_to_the_original(profile: MasterProfile) -> None:
    first = duplicate_achievement(profile, "exp-acme", "achievement-scan")
    middle = _copy_of(first, "achievement-scan")
    second = duplicate_achievement(first, "exp-acme", middle.id)
    last = _copy_of(second, middle.id)

    result = remove_achievement(second, "exp-acme", middle.id)

    survivor = next(a for a in result.experiences[0].achievements if a.id == last.id)
    assert survivor.copy_of == "achievement-scan"


def test_removing_an_original_frees_its_copies(profile: MasterProfile) -> None:
    duplicated = duplicate_achievement(profile, "exp-acme", "achievement-scan")
    copy = _copy_of(duplicated, "achievement-scan")

    result = remove_achievement(duplicated, "exp-acme", "achievement-scan")

    survivor = next(a for a in result.experiences[0].achievements if a.id == copy.id)
    assert survivor.copy_of is None


# ----------------------------------------------------------------- move


def test_move_up_and_down(profile: MasterProfile) -> None:
    assert _ids(move_achievement(profile, "exp-acme", "achievement-llm", -1)) == [
        "achievement-scan",
        "achievement-llm",
        "achievement-triage",
    ]
    assert _ids(move_achievement(profile, "exp-acme", "achievement-scan", 1)) == [
        "achievement-triage",
        "achievement-scan",
        "achievement-llm",
    ]


def test_move_stays_inside_the_job(profile: MasterProfile) -> None:
    original = _ids(profile)

    assert _ids(move_achievement(profile, "exp-acme", "achievement-scan", -1)) == original
    assert _ids(move_achievement(profile, "exp-acme", "achievement-llm", 1)) == original


# --------------------------------------------------------------- safety


def test_no_operation_modifies_the_given_profile(profile: MasterProfile) -> None:
    before = profile.model_dump()

    add_achievement(profile, "exp-acme", "New one.")
    edit_achievement(profile, "exp-acme", "achievement-scan", "Edited.")
    restore_linkedin_text(profile, "exp-acme", "achievement-triage")
    duplicate_achievement(profile, "exp-acme", "achievement-scan")
    remove_achievement(profile, "exp-acme", "achievement-triage")
    move_achievement(profile, "exp-acme", "achievement-llm", -1)

    assert profile.model_dump() == before


def test_unknown_ids_raise_a_clear_error(profile: MasterProfile) -> None:
    by_job = [
        lambda p, e: add_achievement(p, e, "Text."),
        lambda p, e: edit_achievement(p, e, "achievement-scan", "Text."),
        lambda p, e: restore_linkedin_text(p, e, "achievement-triage"),
        lambda p, e: duplicate_achievement(p, e, "achievement-scan"),
        lambda p, e: remove_achievement(p, e, "achievement-scan"),
        lambda p, e: move_achievement(p, e, "achievement-scan", 1),
    ]
    for operation in by_job:
        with pytest.raises(ValueError, match="job no longer exists"):
            operation(profile, "exp-gone")

    by_achievement = [
        lambda p, a: edit_achievement(p, "exp-acme", a, "Text."),
        lambda p, a: restore_linkedin_text(p, "exp-acme", a),
        lambda p, a: duplicate_achievement(p, "exp-acme", a),
        lambda p, a: remove_achievement(p, "exp-acme", a),
        lambda p, a: move_achievement(p, "exp-acme", a, 1),
    ]
    for operation in by_achievement:
        with pytest.raises(ValueError, match="achievement no longer exists"):
            operation(profile, "achievement-gone")

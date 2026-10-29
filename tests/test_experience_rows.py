"""The rows of the Work experience editor in My profile.

Reflex cannot nest a filtered `foreach`, so each job and its achievements travel as one
flat list. The state that saves them runs only in the browser.
"""

import pytest

from cv_generator.app.components.work_experience import work_experience
from cv_generator.app.states.experience_state import achievement_rows
from cv_generator.models.profile import Achievement, Experience, MasterProfile
from cv_generator.services.achievements import add_achievement
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
            ),
            Experience(id="exp-north", company="Northwind", role="Cloud Engineer", start="2019-01", end="2022-02"),
        ],
    )


def test_rows_interleave_each_job_with_its_achievements_and_an_add_row(profile: MasterProfile) -> None:
    assert [(r["row"], r["key"]) for r in achievement_rows(profile)] == [
        ("job", "exp-acme"),
        ("achievement", "exp-acme|achievement-scan"),
        ("achievement", "exp-acme|achievement-triage"),
        ("achievement", "exp-acme|achievement-llm"),
        ("add", "exp-acme|add"),
        ("job", "exp-north"),
        ("add", "exp-north|add"),
    ]


def _counts(profile: MasterProfile) -> list[str]:
    return [r["count"] for r in achievement_rows(profile) if r["row"] == "job"]


def test_job_rows_count_their_achievements(profile: MasterProfile) -> None:
    assert _counts(profile) == ["3 achievements", "No achievements"]

    with_one = add_achievement(profile, "exp-north", "Moved the pipelines to GitHub Actions.")
    assert _counts(with_one) == ["3 achievements", "1 achievement"]


def test_achievement_rows_carry_origin_linkedin_text_and_ends(profile: MasterProfile) -> None:
    rows = [r for r in achievement_rows(profile) if r["row"] == "achievement"]

    assert [r["origin"] for r in rows] == ["linkedin", "edited", "yours"]
    assert [r["linkedin_text"] for r in rows] == [
        "Automated scanning in 120 pipelines.",
        "Improved the triage of findings.",
        "",
    ]
    assert [(r["first"], r["last"]) for r in rows] == [("yes", ""), ("", ""), ("", "yes")]


def test_every_row_carries_the_same_keys(profile: MasterProfile) -> None:
    assert len({tuple(sorted(r)) for r in achievement_rows(profile)}) == 1


def test_the_editor_renders() -> None:
    assert work_experience().render()

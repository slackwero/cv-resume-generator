"""The rows of the Work experience editor in My profile.

Reflex cannot nest a filtered `foreach`, so each job and its achievements travel as one
flat list. What the editor does with them is tested in test_experience_state.py.
"""

import pytest

from cv_generator.app.components.work_experience import work_experience
from cv_generator.app.pages.profile import profile_page
from cv_generator.app.states.experience_state import achievement_rows
from cv_generator.models.profile import Achievement, Experience, MasterProfile
from cv_generator.services.achievements import add_achievement
from tests import bilingual
from tests.test_models_personal import REQUIRED


def sample_profile() -> MasterProfile:
    """A job with one achievement of each origin, and one without achievements nor location."""
    return MasterProfile(
        source_language="en",
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


@pytest.fixture
def profile() -> MasterProfile:
    return sample_profile()


def test_rows_interleave_each_job_with_its_achievements_and_an_add_row(profile: MasterProfile) -> None:
    assert [(r["row"], r["key"]) for r in achievement_rows(profile, "en")] == [
        ("job", "exp-acme"),
        ("achievement", "exp-acme|achievement-scan"),
        ("achievement", "exp-acme|achievement-triage"),
        ("achievement", "exp-acme|achievement-llm"),
        ("add", "exp-acme|add"),
        ("job", "exp-north"),
        ("add", "exp-north|add"),
    ]


def _counts(profile: MasterProfile) -> list[str]:
    return [r["count"] for r in achievement_rows(profile, "en") if r["row"] == "job"]


def test_job_rows_count_their_achievements(profile: MasterProfile) -> None:
    assert _counts(profile) == ["3 achievements", "No achievements"]

    with_one = add_achievement(profile, "exp-north", "Moved the pipelines to GitHub Actions.")
    assert _counts(with_one) == ["3 achievements", "1 achievement"]


def test_achievement_rows_carry_origin_linkedin_text_and_ends(profile: MasterProfile) -> None:
    rows = [r for r in achievement_rows(profile, "en") if r["row"] == "achievement"]

    assert [r["origin"] for r in rows] == ["linkedin", "edited", "yours"]
    assert [r["linkedin_text"] for r in rows] == [
        "Automated scanning in 120 pipelines.",
        "Improved the triage of findings.",
        "",
    ]
    assert [(r["first"], r["last"]) for r in rows] == [("yes", ""), ("", ""), ("", "yes")]


def test_every_row_carries_the_same_keys(profile: MasterProfile) -> None:
    assert len({tuple(sorted(r)) for r in achievement_rows(profile, "en")}) == 1


def test_rows_in_english_are_current_and_the_job_texts_read_only(profile: MasterProfile) -> None:
    job, achievement, *_ = achievement_rows(profile, "en")

    assert (job["role"]["text"], job["role"]["state"], job["role"]["editable"]) == ("DevSecOps Engineer", "", "")
    assert (achievement["text"], achievement["own"], achievement["state"], achievement["reference"]) == (
        "Automated scanning in 120 pipelines.",
        "Automated scanning in 120 pipelines.",
        "",
        "",
    )


def test_rows_in_spanish_show_the_english_marked_pending_translation() -> None:
    job, achievement, _ = achievement_rows(bilingual.sample_profile(), "es")

    def version(row: dict[str, str]) -> tuple[str, ...]:
        return row["text"], row["own"], row["state"], row["reference"], row["reference_language"]

    # The English stands in for each missing Spanish text, and an editor starts empty.
    assert version(job["role"]) == ("Platform Engineer", "", "missing", "Platform Engineer", "English")
    assert version(job["location"]) == ("Santiago, Chile", "", "missing", "Santiago, Chile", "English")
    assert version(achievement) == ("Cut deploy time by 40%", "", "missing", "Cut deploy time by 40%", "English")
    # Role and location are written by hand in Spanish only, where LinkedIn does not write them.
    assert (job["role"]["editable"], job["location"]["editable"]) == ("yes", "yes")
    assert (job["role"]["copyable"], job["location"]["copyable"]) == ("yes", "yes")


def test_a_location_empty_in_english_is_not_written_in_spanish(profile: MasterProfile) -> None:
    """Spanish only, it would stay pending in English, where nothing writes it by hand."""
    north = next(row for row in achievement_rows(profile, "es") if row["key"] == "exp-north")

    assert (north["location"]["text"], north["location"]["editable"]) == ("", "")
    assert north["role"]["editable"] == "yes"


def test_the_editor_renders() -> None:
    assert work_experience().render()


def test_the_job_texts_save_on_blur_and_on_enter() -> None:
    """Enter goes through a form whose handler Reflex compiles outside the `foreach`, with the hooks."""
    editor = work_experience()
    rendered = str(editor.render())
    hooks = " ".join(str(hook) for hook in editor._get_all_hooks())

    for handler in ("save_job_field", "confirm_job_field", "same_job_field"):
        assert f"experience_state.{handler}" in rendered
    assert "experience_state.job_field_from_form" in hooks


def test_one_click_on_the_switch_moves_my_profile_and_then_the_work_experience() -> None:
    rendered = str(profile_page().render())
    spanish = rendered[rendered.index('id:"content-language-es"') :]
    click = spanish[: spanish.index("ref:")]

    assert click.index("profile_state.switch_language") < click.index("experience_state.show_language")

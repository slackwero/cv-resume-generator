import pytest
from pydantic import ValidationError

from cv_generator.models.profile import Achievement, Experience, MasterProfile, Skill
from tests.test_models_personal import REQUIRED


def test_assigns_an_automatic_id_to_each_item() -> None:
    achievement = Achievement(text="Cut deployment time from 40 to 6 minutes")

    assert achievement.id.startswith("achievement-")


def test_two_items_of_the_same_kind_get_different_ids() -> None:
    first = Achievement(text="Automated the pipeline SAST scanning")
    second_one = Achievement(text="Automated the pipeline SAST scanning")

    assert first.id != second_one.id


def test_keeps_the_existing_id_when_loading_from_json() -> None:
    achievement = Achievement(id="achievement-abc12345", text="Led the Kubernetes migration")

    assert achievement.id == "achievement-abc12345"


def test_id_prefixes_tell_the_item_kind_apart() -> None:
    experience = Experience(company="Acme Airlines", role="DevSecOps", start="2022-03")
    skill = Skill(name="Kubernetes")

    assert experience.id.startswith("exp-")
    assert skill.id.startswith("skill-")


@pytest.mark.parametrize("invalid_date", ["March 2022", "2022", "2022-3", "22-03", "2022-13"])
def test_rejects_dates_that_are_not_year_month(invalid_date: str) -> None:
    with pytest.raises(ValidationError):
        Experience(company="Acme Airlines", role="DevSecOps", start=invalid_date)


def test_a_current_experience_has_no_end_date() -> None:
    experience = Experience(company="Acme Airlines", role="DevSecOps", start="2022-03", current=True)

    assert experience.end is None


def test_rejects_a_current_experience_with_an_end_date() -> None:
    with pytest.raises(ValidationError, match="current"):
        Experience(
            company="Acme Airlines",
            role="DevSecOps",
            start="2022-03",
            end="2024-08",
            current=True,
        )


def test_a_new_master_profile_requires_only_personal_info() -> None:
    profile = MasterProfile(personal=REQUIRED)

    assert profile.experiences == []
    assert profile.skills == []
    assert profile.schema_version == 1


def test_master_profile_survives_a_json_round_trip() -> None:
    original = MasterProfile(
        personal=REQUIRED,
        experiences=[
            Experience(
                company="Acme Airlines",
                role="DevSecOps Engineer",
                start="2022-03",
                current=True,
                achievements=[Achievement(text="Cut critical SAST findings by 80%")],
            )
        ],
    )

    recovered = MasterProfile.model_validate_json(original.model_dump_json())

    assert recovered == original
    assert recovered.experiences[0].achievements[0].id == original.experiences[0].achievements[0].id


def test_a_current_job_says_it_is_current() -> None:
    """An open range ("2024-09 —") does not say whether the job continues or the date is missing."""
    job = Experience(company="Fabrikam", role="Security Architect", start="2024-09", current=True)

    assert job.period() == "2024-09 — present"


def test_a_closed_job_shows_both_dates() -> None:
    job = Experience(company="Northwind", role="Platform Engineer", start="2020-04", end="2024-08")

    assert job.period() == "2020-04 — 2024-08"

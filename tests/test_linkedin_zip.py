"""LinkedIn's official export: a ZIP with one CSV per section."""

import zipfile
from pathlib import Path

import pytest

from cv_generator.importers.base import ProfileDraft
from cv_generator.importers.linkedin_zip import import_from_zip, parse_export

PROFILE_CSV = (
    "First Name,Last Name,Maiden Name,Address,Birth Date,Headline,Summary,Industry,"
    "Zip Code,Geo Location,Twitter Handles,Websites,Instant Messengers\n"
    'Jane,Doe,,,,Platform Engineer | SRE,"Systems engineer with ten years of '
    "experience running infrastructure and automating operations for the logistics "
    'and media industries.",Information Technology,,"Madrid, Spain",,,\n'
)

POSITIONS_CSV = (
    "Company Name,Title,Description,Location,Started On,Finished On\n"
    '"Company One","Platform Engineer","- Moved the internal services to containers\n'
    '- Wrote capacity alerts with Prometheus","Madrid","Apr 2022",\n'
    '"Acme Bank","Technical Lead","Ran the server inventory for the bank.",'
    '"Valencia","Feb 2015","Apr 2019"\n'
    '"Acme Bank","Full Stack Engineer","Automated internal reports with scripts.",'
    '"Valencia","Mar 2013","Jan 2015"\n'
)

EDUCATION_CSV = (
    "School Name,Start Date,End Date,Notes,Degree Name,Activities\n"
    '"Example University","2007","2012",,"Telecommunications Engineering",\n'
)

SKILLS_CSV = "Name\nLinux\nTerraform\nGo\n"
LANGUAGES_CSV = "Name,Proficiency\nSpanish,Native or bilingual proficiency\nEnglish,Professional working proficiency\n"
CERTIFICATIONS_CSV = (
    "Name,Url,Authority,Started On,Finished On,License Number\n"
    '"AWS Certified SysOps Administrator",,"Amazon Web Services","Mar 2024",,\n'
)
EMAILS_CSV = "Email Address,Confirmed,Primary,Updated On\nsecondary@example.com,Yes,No,\nemail@example.com,Yes,Yes,\n"

EXPORT = {
    "Profile.csv": PROFILE_CSV,
    "Positions.csv": POSITIONS_CSV,
    "Education.csv": EDUCATION_CSV,
    "Skills.csv": SKILLS_CSV,
    "Languages.csv": LANGUAGES_CSV,
    "Certifications.csv": CERTIFICATIONS_CSV,
    "Email Addresses.csv": EMAILS_CSV,
}


@pytest.fixture
def draft() -> ProfileDraft:
    return parse_export(EXPORT)


def test_takes_the_name_and_headline(draft: ProfileDraft) -> None:
    assert draft.personal.first_name == "Jane"
    assert draft.personal.last_name == "Doe"
    assert draft.personal.profession == "Platform Engineer | SRE"


def test_takes_the_location_and_the_primary_email(draft: ProfileDraft) -> None:
    assert draft.personal.country == "Madrid, Spain"
    assert draft.personal.email == "email@example.com"


def test_turns_the_summary_into_a_profile_text(draft: ProfileDraft) -> None:
    assert len(draft.profile_texts) == 1
    assert draft.profile_texts[0].text.startswith("Systems engineer with ten years")


def test_recognizes_every_position(draft: ProfileDraft) -> None:
    assert [e.role for e in draft.experiences] == [
        "Platform Engineer",
        "Technical Lead",
        "Full Stack Engineer",
    ]


def test_converts_abbreviated_months_to_year_month(draft: ProfileDraft) -> None:
    first_one = draft.experiences[0]

    assert first_one.start == "2022-04"
    assert first_one.end is None
    assert first_one.current is True, "with no end date, the job is still current"


def test_a_closed_position_keeps_both_dates(draft: ProfileDraft) -> None:
    second = draft.experiences[1]

    assert second.start == "2015-02"
    assert second.end == "2019-04"
    assert second.current is False


def test_splits_the_description_into_achievements(draft: ProfileDraft) -> None:
    achievements = [achievement.text for achievement in draft.experiences[0].achievements]

    assert achievements == [
        "Moved the internal services to containers",
        "Wrote capacity alerts with Prometheus",
    ]


def test_a_description_without_bullets_stays_one_achievement(draft: ProfileDraft) -> None:
    achievements = draft.experiences[1].achievements

    assert len(achievements) == 1
    assert achievements[0].text == "Ran the server inventory for the bank."


def test_records_each_achievement_original_text(draft: ProfileDraft) -> None:
    """Without the origin, editing an achievement would make the next sync duplicate it."""
    achievement = draft.experiences[0].achievements[0]

    assert achievement.imported_value == achievement.text


def test_extracts_skills_languages_education_and_courses(draft: ProfileDraft) -> None:
    assert [h.name for h in draft.skills] == ["Linux", "Terraform", "Go"]
    assert [(i.language, i.level) for i in draft.languages][0] == (
        "Spanish",
        "Native or bilingual proficiency",
    )
    assert draft.education[0].institution == "Example University"
    assert draft.education[0].title == "Telecommunications Engineering"
    assert draft.courses[0].name == "AWS Certified SysOps Administrator"
    assert draft.courses[0].year == 2024


def test_detects_the_content_language(draft: ProfileDraft) -> None:
    assert draft.detected_language == "en"


def test_an_export_missing_some_csvs_does_not_crash() -> None:
    draft = parse_export({"Skills.csv": SKILLS_CSV})

    assert [h.name for h in draft.skills] == ["Linux", "Terraform", "Go"]
    assert draft.experiences == []


def test_reads_the_zip_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in EXPORT.items():
            zf.writestr(name, content)

    draft = import_from_zip(path)

    assert draft.personal.first_name == "Jane"
    assert len(draft.experiences) == 3


def test_finds_the_csvs_even_in_a_subfolder(tmp_path: Path) -> None:
    """Some exports come with everything inside a folder."""
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in EXPORT.items():
            zf.writestr(f"Basic_LinkedInDataExport_01-01-2026/{name}", content)

    draft = import_from_zip(path)

    assert draft.personal.first_name == "Jane"
    assert len(draft.experiences) == 3


def test_ignores_paths_that_escape_the_zip(tmp_path: Path) -> None:
    """A malicious zip must not be able to make anything outside itself be read."""
    path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("../../outside/Skills.csv", SKILLS_CSV)
        zf.writestr("Profile.csv", PROFILE_CSV)

    draft = import_from_zip(path)

    assert draft.skills == [], "it must not read a CSV whose path leaves the archive"
    assert draft.personal.first_name == "Jane"


def test_records_the_name_each_skill_came_with(draft: ProfileDraft) -> None:
    """Without the origin, renaming a skill makes LinkedIn propose it again as new."""
    assert all(skill.imported_value == skill.name for skill in draft.skills)

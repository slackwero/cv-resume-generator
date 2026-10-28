"""Importer for LinkedIn's official export.

It is the main way to populate the profile: you request it on LinkedIn (Settings ->
Data privacy -> Get a copy of your data) and a ZIP arrives with one CSV per section.
Unlike the PDF, the data here comes structured, so there are no heuristics: each field
is in its column.
"""

import csv
import io
import zipfile
from pathlib import Path

from cv_generator.importers.base import (
    PartialPersonalInfo,
    ProfileDraft,
    split_into_achievements,
)
from cv_generator.models.profile import (
    Achievement,
    Course,
    Education,
    Experience,
    Language,
    ProfileText,
    Skill,
)
from cv_generator.rendering.i18n import available_languages, detect_language, load_language

PROFILE_FILE = "profile.csv"
POSITIONS_FILE = "positions.csv"
EDUCATION_FILE = "education.csv"
SKILLS_FILE = "skills.csv"
LANGUAGES_FILE = "languages.csv"
CERTIFICATIONS_FILE = "certifications.csv"
EMAILS_FILE = "email addresses.csv"

# When LinkedIn only gives the start year, January is assumed. The model requires
# year-month, and losing the whole experience would be worse than approximating the month.
ASSUMED_MONTH = "01"


def _month_map() -> dict[str, int]:
    """Month number by its three-letter abbreviation, in every language."""
    return {
        month[:3].lower(): number
        for language in available_languages()
        for number, month in enumerate(load_language(language).months, start=1)
    }


def _to_year_month(value: str) -> str | None:
    """Turns "Mar 2021" or "2021" into the YYYY-MM format. None if there is nothing."""
    parts = value.strip().split()
    if not parts:
        return None

    year = parts[-1]
    if not year.isdigit() or len(year) != 4:  # noqa: PLR2004
        return None

    if len(parts) == 1:
        return f"{year}-{ASSUMED_MONTH}"

    number = _month_map().get(parts[0][:3].lower())
    return f"{year}-{number:02d}" if number else f"{year}-{ASSUMED_MONTH}"


def _rows(content: str | None) -> list[dict[str, str]]:
    """Reads a CSV into dictionaries, tolerating a missing file."""
    if not content:
        return []
    return [
        {(key or "").strip(): (value or "").strip() for key, value in row.items()}
        for row in csv.DictReader(io.StringIO(content))
    ]


def _first(rows: list[dict[str, str]]) -> dict[str, str]:
    return rows[0] if rows else {}


def _parse_experiences(rows: list[dict[str, str]]) -> list[Experience]:
    """Each row of Positions.csv is a job, with its description in one column."""
    experiences: list[Experience] = []

    for row in rows:
        start = _to_year_month(row.get("Started On", ""))
        if not row.get("Title") or start is None:
            continue

        end = _to_year_month(row.get("Finished On", ""))
        achievements = split_into_achievements(row.get("Description", "").splitlines())
        experiences.append(
            Experience(
                company=row.get("Company Name") or "No company",
                role=row["Title"],
                location=row.get("Location") or None,
                start=start,
                end=end,
                current=end is None,
                # The origin is recorded so that a future sync can tell your own edit apart from a
                # change made on LinkedIn.
                achievements=[Achievement(text=text, imported_value=text) for text in achievements],
            )
        )

    return experiences


def _parse_education(rows: list[dict[str, str]]) -> list[Education]:
    return [
        Education(
            institution=row["School Name"],
            title=row.get("Degree Name") or row["School Name"],
            start=_to_year_month(row.get("Start Date", "")),
            end=_to_year_month(row.get("End Date", "")),
        )
        for row in rows
        if row.get("School Name")
    ]


def _parse_courses(rows: list[dict[str, str]]) -> list[Course]:
    courses: list[Course] = []
    for row in rows:
        if not row.get("Name"):
            continue
        year_month = _to_year_month(row.get("Started On", ""))
        courses.append(
            Course(
                name=row["Name"],
                institution=row.get("Authority") or None,
                year=int(year_month[:4]) if year_month else None,
            )
        )
    return courses


def _primary_email(rows: list[dict[str, str]]) -> str | None:
    """LinkedIn marks one of the email addresses as primary; that is the one that matters."""
    main_items = [f["Email Address"] for f in rows if f.get("Primary", "").lower() == "yes"]
    if main_items:
        return main_items[0]
    return rows[0]["Email Address"] if rows and rows[0].get("Email Address") else None


def parse_export(files: dict[str, str]) -> ProfileDraft:
    """Builds a profile draft from the export's CSVs.

    File names are compared in lowercase: LinkedIn has changed their capitalization
    between export versions.
    """
    by_name = {name.lower(): content for name, content in files.items()}

    profile = _first(_rows(by_name.get(PROFILE_FILE)))
    experiences = _parse_experiences(_rows(by_name.get(POSITIONS_FILE)))
    summary = profile.get("Summary", "")

    user_text = " ".join([summary] + [achievement.text for e in experiences for achievement in e.achievements])

    return ProfileDraft(
        detected_language=detect_language(user_text),
        personal=PartialPersonalInfo(
            first_name=profile.get("First Name") or None,
            last_name=profile.get("Last Name") or None,
            profession=profile.get("Headline") or None,
            email=_primary_email(_rows(by_name.get(EMAILS_FILE))),
            website=profile.get("Websites") or None,
            address=profile.get("Address") or None,
            country=profile.get("Geo Location") or None,
        ),
        profile_texts=[ProfileText(text=summary, imported_value=summary)] if summary else [],
        experiences=experiences,
        education=_parse_education(_rows(by_name.get(EDUCATION_FILE))),
        courses=_parse_courses(_rows(by_name.get(CERTIFICATIONS_FILE))),
        languages=[
            Language(language=row["Name"], level=row.get("Proficiency") or None)
            for row in _rows(by_name.get(LANGUAGES_FILE))
            if row.get("Name")
        ],
        skills=[
            Skill(name=row["Name"], imported_value=row["Name"])
            for row in _rows(by_name.get(SKILLS_FILE))
            if row.get("Name")
        ],
    )


def _is_safe_path(name: str) -> bool:
    """Drops entries that point outside the ZIP itself."""
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def import_from_zip(path: Path) -> ProfileDraft:
    """Reads the LinkedIn export ZIP and returns the extracted draft.

    The CSVs are located by their final name, because some exports deliver them inside
    a folder. Entries with paths that escape the archive are ignored: a ZIP is external
    content and must not be able to direct a read.
    """
    files: dict[str, str] = {}

    with zipfile.ZipFile(path) as zf:
        for element in zf.infolist():
            if element.is_dir() or not _is_safe_path(element.filename):
                continue
            name = Path(element.filename).name
            files[name] = zf.read(element).decode("utf-8", errors="replace")

    return parse_export(files)

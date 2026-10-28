"""Importer for the PDF LinkedIn generates with the profile's "Save to PDF".

The PDF has no semantic structure: it is text with breaks by column width, page
markers in between, and the sidebar mixed with the body. The parser anchors on the
only unmistakable signal, each position's date line, and works out the rest from it.

It is best-effort by nature: the user reviews and fixes the result before merging it
into their master profile.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from cv_generator.importers.base import (
    PartialPersonalInfo,
    ProfileDraft,
    split_into_achievements,
)
from cv_generator.models.profile import Achievement, Education, Experience, Language, ProfileText, Skill
from cv_generator.rendering.i18n import available_languages, detect_language, load_language

# LinkedIn translates the headings into the account's language, not the content's.
HEADINGS = {
    "contact": ("Contactar", "Contact"),
    "top_skills": ("Aptitudes principales", "Top Skills"),
    "languages": ("Languages", "Idiomas"),
    "summary_text": ("Extracto", "Summary"),
    "experience": ("Experiencia", "Experience"),
    "education": ("Educación", "Education"),
    "certifications": ("Certificaciones", "Certifications"),
}
SIDEBAR_SECTIONS = ("contact", "top_skills", "languages")

PAGE_PATTERN = re.compile(r"^Page \d+ of \d+$")
# LinkedIn inserts non-breaking spaces inside the titles.
UNICODE_SPACES_PATTERN = re.compile(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LEVEL_PATTERN = re.compile(r"^(?P<value>.+?)\s*\((?P<level>[^()]+)\)$")
GROUPING_PATTERN = re.compile(r"^\d+\s+\w+(\s+\d+\s+\w+)?$")
STUDY_YEARS_PATTERN = re.compile(r"^(?P<title>.+?)\s*·?\s*\(\s*\d{4}.*\)$")

# "abril de 2022 - Present (3 años 7 meses)" / "March 2021 - February 2023 (1 year)"
_MONTH = r"[^\W\d_]+"
DATES_PATTERN = re.compile(
    rf"^(?P<start_month>{_MONTH})\s+(?:de\s+)?(?P<start_year>\d{{4}})\s*-\s*"
    rf"(?:(?P<present>Present|Actualidad|el actual)"
    rf"|(?P<end_month>{_MONTH})\s+(?:de\s+)?(?P<end_year>\d{{4}}))"
    r"\s*\(.*\)$",
    re.IGNORECASE,
)

MAX_LOCATION_LENGTH = 60
# Beyond that length, the location is only recognized by its shape: places separated by
# commas, each one capitalized, like "Provincia de Santa Cruz de Tenerife,
# Comunidad Autónoma de Canarias, España". A description with commas always has some lowercase stretch.
MAX_PLACE_LIST_LENGTH = 90
MAX_COMPANY_WORDS = 6
ABBREVIATION_PATTERN = re.compile(r"\b(?:[A-Z]\.){2,}$")


def _month_map() -> dict[str, int]:
    """Month number by name, in every language with an installed translation."""
    return {
        month.lower(): number
        for language in available_languages()
        for number, month in enumerate(load_language(language).months, start=1)
    }


def _to_year_month(month: str, year: str) -> str | None:
    """Turns "marzo", "2021" into "2020-04". Returns None if the month is not recognized."""
    number = _month_map().get(month.lower())
    return None if number is None else f"{year}-{number:02d}"


def _clean(text: str) -> list[str]:
    """Normalizes spaces and drops empty lines and the "Page N of M" markers."""
    normalized = UNICODE_SPACES_PATTERN.sub(" ", text)
    lines = (line.strip() for line in normalized.splitlines())
    return [line for line in lines if line and not PAGE_PATTERN.match(line)]


def _heading_key(line: str) -> str | None:
    """Returns the section this line opens, if it is a known heading."""
    for key, titles in HEADINGS.items():
        if line in titles:
            return key
    return None


def _split_into_blocks(lines: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Groups the lines under the heading that precedes them, keeping their order."""
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None

    for line in lines:
        key = _heading_key(line)
        if key is not None:
            current = key
            blocks.setdefault(key, [])
            if key not in order:
                order.append(key)
        elif current is not None:
            blocks[current].append(line)

    return blocks, order


def _split_header(blocks: dict[str, list[str]], order: list[str]) -> list[str]:
    """Recovers name, headline and location, which have no heading of their own.

    In the PDF that block ends up stuck to the end of the sidebar's last section. It is
    cut at the first line that no longer fits that section's format.
    """
    sides = [key for key in order if key in SIDEBAR_SECTIONS]
    if not sides:
        return []

    last = sides[-1]
    content = blocks[last]
    fits = LEVEL_PATTERN.match if last == "languages" else _looks_like_skill

    cut = len(content)
    for index, line in enumerate(content):
        if not fits(line):
            cut = index
            break

    blocks[last] = content[:cut]
    return content[cut:]


def _looks_like_skill(line: str) -> bool:
    """A skill is short and carries no headline separators nor location commas."""
    return len(line) <= 45 and "|" not in line and "," not in line


def _join_continuations(lines: list[str]) -> list[str]:
    """Joins the lines the PDF broke by column width.

    A line that starts in lowercase or with a parenthesis continues the previous one.
    """
    joined: list[str] = []
    for line in lines:
        continues = joined and (line[0].islower() or line.startswith("("))
        if continues:
            joined[-1] = f"{joined[-1]} {line}"
        else:
            joined.append(line)
    return joined


def _parse_contact(lines: list[str]) -> tuple[str | None, str | None]:
    """Separates the email from the profile link.

    The email is looked for before joining anything: the LinkedIn URL comes broken and
    its second half starts in lowercase, so joining first would swallow it.
    """
    email = next((line for line in lines if EMAIL_PATTERN.match(line)), None)
    rest = [line for line in lines if not EMAIL_PATTERN.match(line)]
    site = "".join(rest).replace(" ", "").replace("(LinkedIn)", "")
    return email, site or None


def _parse_header(header: list[str]) -> tuple[str, str, str]:
    """Returns full name, headline and location from the header block."""
    if not header:
        return "", "", ""
    if len(header) == 1:
        return header[0], "", ""

    name, *rest = header
    location = rest[-1] if len(rest) > 1 else ""
    headline = " ".join(rest[:-1]) if len(rest) > 1 else rest[0]
    return name, headline, location


def _looks_like_company(line: str) -> bool:
    """Tells a company name apart from the end of the previous description.

    A company is short and is not a bullet. It ends in a period only when that period
    closes an abbreviation like "S.A." or "C.A.", not a sentence.
    """
    if line.startswith("-") or len(line.split()) > MAX_COMPANY_WORDS:
        return False
    if not line.endswith("."):
        return True
    return bool(ABBREVIATION_PATTERN.search(line))


def _header_start(lines: list[str], date_index: int) -> int:
    """First line of an entry's header.

    Between the end of a description and the next position there are 0, 1 or 2 lines:
    none if it is another position at the same company, one if a new company starts,
    and two when LinkedIn adds the total time accumulated at that company.
    """
    role = date_index - 1
    previous = role - 1
    if previous >= 0 and GROUPING_PATTERN.match(lines[previous]):
        return max(previous - 1, 0)
    if previous >= 0 and _looks_like_company(lines[previous]):
        return previous
    return role


def _parse_experiences(lines: list[str]) -> list[Experience]:
    """Rebuilds the positions using the date lines as anchors.

    The date line is the only unmistakable signal in the PDF: the position title is
    always the line right before it, and everything else is worked out around it.
    """
    date_indices = [index for index, line in enumerate(lines) if DATES_PATTERN.match(line)]
    # The section's longest line gives the column width, against which we measure whether a
    # line reached the margin or ended earlier because the user wrote it that way.
    column_width = max(map(len, lines), default=0)
    experiences: list[Experience] = []
    current_company = ""

    for position, index in enumerate(date_indices):
        header_start = _header_start(lines, index)
        if header_start < index - 1:
            current_company = lines[header_start]

        has_next = position + 1 < len(date_indices)
        description_end = _header_start(lines, date_indices[position + 1]) if has_next else len(lines)
        location, description = _split_location(lines[index + 1 : description_end])

        experiences.append(
            Experience(
                company=current_company or "No company",
                role=lines[index - 1],
                location=location,
                achievements=[
                    # The origin is recorded so that a future sync can tell your edit apart from a change
                    # made on LinkedIn.
                    Achievement(text=text, imported_value=text)
                    # The PDF is extracted from an already laid out page: a long sentence arrives split by
                    # the width, and those parts do have to be joined again.
                    for text in split_into_achievements(description, column_width=column_width)
                ],
                **_parse_dates(lines[index]),
            )
        )

    return experiences


def _looks_like_location(line: str) -> bool:
    """No bullet and no final period, and short or shaped like a list of places."""
    if line.startswith("-") or line.endswith("."):
        return False
    if len(line) <= MAX_LOCATION_LENGTH:
        return True

    places = [place.strip() for place in line.split(",")]
    return len(line) <= MAX_PLACE_LIST_LENGTH and len(places) > 1 and all(place[:1].isupper() for place in places)


def _split_location(body: list[str]) -> tuple[str | None, list[str]]:
    """The location, if present, is the first line."""
    if not body:
        return None, []

    first_one = body[0]
    return (first_one, body[1:]) if _looks_like_location(first_one) else (None, body)


def _parse_dates(line: str) -> dict[str, object]:
    """Translates LinkedIn's date line into the model fields."""
    found = DATES_PATTERN.match(line)
    if found is None:
        return {"start": "1970-01", "end": None, "current": False}

    data = found.groupdict()
    start = _to_year_month(data["start_month"], data["start_year"]) or "1970-01"
    if data["present"]:
        return {"start": start, "end": None, "current": True}

    end = _to_year_month(data["end_month"], data["end_year"])
    return {"start": start, "end": end, "current": False}


def _parse_education(lines: list[str]) -> list[Education]:
    """Each study takes two lines: the institution, and the title with its years."""
    joined = _join_continuations(lines)
    studies: list[Education] = []

    for index, line in enumerate(joined):
        found = STUDY_YEARS_PATTERN.match(line)
        if found is None or index == 0:
            continue
        studies.append(Education(institution=joined[index - 1], title=found.group("title").strip(" ·")))

    return studies


def parse_linkedin_profile(text: str) -> ProfileDraft:
    """Builds a profile draft from the LinkedIn PDF text."""
    blocks, order = _split_into_blocks(_clean(text))
    header = _split_header(blocks, order)

    full_name, headline, location = _parse_header(header)
    first_name, _, last_name = full_name.partition(" ")
    email, website = _parse_contact(blocks.get("contact", []))

    summary_text = " ".join(blocks.get("summary_text", []))
    languages = [
        Language(language=m.group("value"), level=m.group("level"))
        for m in (LEVEL_PATTERN.match(line) for line in blocks.get("languages", []))
        if m
    ]

    experiences = _parse_experiences(blocks.get("experience", []))
    user_text = " ".join([summary_text] + [achievement.text for e in experiences for achievement in e.achievements])

    return ProfileDraft(
        detected_language=detect_language(user_text),
        personal=PartialPersonalInfo(
            first_name=first_name or None,
            last_name=last_name or None,
            profession=headline or None,
            email=email,
            website=website,
            country=location or None,
        ),
        profile_texts=[ProfileText(text=summary_text, imported_value=summary_text)] if summary_text else [],
        experiences=experiences,
        education=_parse_education(blocks.get("education", [])),
        languages=languages,
        skills=[Skill(name=n, imported_value=n) for n in _join_continuations(blocks.get("top_skills", []))],
    )


def import_from_pdf(path: Path) -> ProfileDraft:
    """Reads the PDF LinkedIn generates from the profile and returns the extracted draft."""
    reader = PdfReader(path)
    return parse_linkedin_profile("\n".join(page.extract_text() or "" for page in reader.pages))

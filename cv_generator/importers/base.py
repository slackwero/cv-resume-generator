"""Common contract of the LinkedIn importers.

Both importers (ZIP export and profile PDF) produce the same `ProfileDraft`. A draft
never replaces the master profile: it is merged into it, keeping the existing ids and
whatever the user edited by hand.
"""

import re

from pydantic import BaseModel, Field

from cv_generator.models.profile import (
    Course,
    Education,
    Experience,
    Language,
    ProfileText,
    Skill,
)


class PartialPersonalInfo(BaseModel):
    """Contact details as they come from LinkedIn.

    Everything is optional: LinkedIn does not expose the phone, and the user completes
    the required fields when merging the draft into their profile.
    """

    first_name: str | None = None
    last_name: str | None = None
    profession: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    country: str | None = None


class ProfileDraft(BaseModel):
    """What an importer managed to extract, before merging it into the master profile."""

    # The language the content is written in, not the language of LinkedIn's labels.
    detected_language: str = "en"
    personal: PartialPersonalInfo = Field(default_factory=PartialPersonalInfo)
    profile_texts: list[ProfileText] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    courses: list[Course] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)


BULLETS = ("- ", "• ", "* ")

# If the previous line ends in one of these, it was already closed: what follows starts
# something new, it does not continue the sentence.
CLOSINGS = (".", ":", ";", "!", "?")

# A line that takes at least this fraction of the column reached the margin: the break
# was put there by the layout, not by the user. With a proportional font, the length in
# characters of a full line varies; in the user's real PDF it went from 64 to 83.
FULL_LINE_FRACTION = 0.7

# "Tech stack: Go", "Tools: GitLab": a few words and a colon open a block of their own.
LABEL_PATTERN = re.compile(r"^[^\W\d_][^\s:,]*(?: [^\s:,]+){0,2}:(?:\s|$)")


def _is_label(line: str) -> bool:
    return line[:1].isupper() and bool(LABEL_PATTERN.match(line))


def _continues_sentence(previous: str, line: str, column_width: int) -> bool:
    """Whether this line is the same sentence as the previous one, split by the page width.

    It is only used with sources that wrap the text when it is extracted. A closed
    sentence does not continue, and a label like "Tech stack:" always opens a block of
    its own. Beyond that, one of two signals is enough: the line starts in lowercase, or
    the previous one reached the margin. Lowercase alone is not enough: in a technical
    CV the break often falls right before a proper name ("ArgoCD", "GCP").
    """
    if not previous or previous.endswith(CLOSINGS) or _is_label(line):
        return False
    return line[:1].islower() or len(previous) >= column_width * FULL_LINE_FRACTION


def split_into_achievements(lines: list[str], *, column_width: int | None = None) -> list[str]:
    """Splits a job description into separate achievements, without rewriting the text.

    Each line is an achievement. A line without a bullet is not glued to the previous
    one: doing so fabricated sentences the user never wrote, and the typical case was
    the "Tech stack: ..." block merged into the last achievement.

    Args:
        lines: the description, as it comes from the source.
        column_width: length, in characters, of the source's longest line. Pass it only
            if the source splits sentences by width: the PDF is extracted from an
            already laid out page and needs it; the ZIP export keeps the line breaks the
            user wrote and does not. Without it nothing is joined.
    """
    cleaned = [line.strip() for line in lines if line.strip()]
    if not cleaned:
        return []

    achievements: list[str] = []
    previous = ""
    for line in cleaned:
        if line.startswith(BULLETS):
            achievements.append(line[2:].strip())
        elif achievements and column_width is not None and _continues_sentence(previous, line, column_width):
            achievements[-1] = f"{achievements[-1]} {line}"
        else:
            achievements.append(line)
        previous = line
    return achievements

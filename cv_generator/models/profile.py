"""Master profile models: the source of truth for the professional information.

Every item has a stable, unique `id`. That id is what lets a CV reference by
selection the achievements and skills it includes, and lets the history memory
propose the same selection in a future application.
"""

import uuid
from collections.abc import Callable
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Work and education dates are written as year-month: "2022-03".
YearMonth = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]

# The photo travels embedded as a base64 JPEG, never as a path or URL: it goes into the
# template's `src`, and WeasyPrint would resolve a path by reading the disk and a URL by
# fetching it from the network. Embedded, every history snapshot also carries its own copy.
EmbeddedPhoto = Annotated[str, StringConstraints(pattern=r"^data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}$")]


def _generate_id(prefix: str) -> Callable[[], str]:
    """Builds the id factory for an item kind, with its distinctive prefix."""
    return lambda: f"{prefix}-{uuid.uuid4().hex[:8]}"


class PersonalInfo(BaseModel):
    """Identification and contact details at the top of the CV.

    Only first name, last name, profession, phone and email are required; the rest
    is shown only if the template supports it and the user filled it in.
    """

    first_name: RequiredText
    last_name: RequiredText
    profession: RequiredText
    phone: RequiredText
    email: RequiredText

    website: str | None = None
    birth_date: date | None = None
    address: str | None = None
    country: str | None = None
    photo: EmbeddedPhoto | None = None

    def compute_age(self, today: date) -> int | None:
        """Derives the age from the birth date. The age is never stored."""
        if self.birth_date is None:
            return None

        birth = self.birth_date
        had_birthday_this_year = (today.month, today.day) >= (birth.month, birth.day)
        return today.year - birth.year - (0 if had_birthday_this_year else 1)


class ProfileText(BaseModel):
    """A presentation text from the pool. One is chosen per CV, depending on the application."""

    id: str = Field(default_factory=_generate_id("profile"))
    text: RequiredText
    imported_value: str | None = None


class Achievement(BaseModel):
    """A single achievement of a work experience, written once and reusable."""

    id: str = Field(default_factory=_generate_id("achievement"))
    text: RequiredText

    # The text as it came from LinkedIn the last time. Comparing `text` against this
    # field is what tells "I edited it" apart from "it changed on LinkedIn" when syncing.
    imported_value: str | None = None


class Experience(BaseModel):
    """A job with its pool of achievements."""

    id: str = Field(default_factory=_generate_id("exp"))
    company: RequiredText
    role: RequiredText
    location: str | None = None
    start: YearMonth
    end: YearMonth | None = None
    current: bool = False
    achievements: list[Achievement] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_date_consistency(self) -> "Experience":
        if self.current and self.end is not None:
            raise ValueError("an experience marked as current cannot have an end date")
        if self.end is not None and self.end < self.start:
            raise ValueError("the end date cannot be earlier than the start date")
        return self

    def period(self) -> str:
        """The dates as they read on screen: "2020-04 — 2024-08" or "2024-09 — present".

        An open range ("2024-09 —") does not tell a current job apart from one that is
        missing its end date.
        """
        return f"{self.start} — {'present' if self.current else self.end or ''}".rstrip()


class Education(BaseModel):
    """A formal study."""

    id: str = Field(default_factory=_generate_id("edu"))
    institution: RequiredText
    title: RequiredText
    start: YearMonth | None = None
    end: YearMonth | None = None
    in_progress: bool = False


class Course(BaseModel):
    """A course or certification."""

    id: str = Field(default_factory=_generate_id("course"))
    name: RequiredText
    institution: str | None = None
    year: int | None = None


class Language(BaseModel):
    """A language and the declared level."""

    id: str = Field(default_factory=_generate_id("language"))
    language: RequiredText
    level: str | None = None


class Skill(BaseModel):
    """A skill or technical knowledge."""

    id: str = Field(default_factory=_generate_id("skill"))
    name: RequiredText
    category: str | None = None
    level: str | None = None

    # The name as it came from LinkedIn. If you rename it here, this is what lets the next
    # sync recognize it instead of proposing it as new.
    imported_value: str | None = None


class Hobby(BaseModel):
    """A hobby or personal interest."""

    id: str = Field(default_factory=_generate_id("hobby"))
    text: RequiredText


class Reference(BaseModel):
    """A personal or professional reference."""

    id: str = Field(default_factory=_generate_id("ref"))
    name: RequiredText
    relationship: str | None = None
    phone: str | None = None
    email: str | None = None


class MasterProfile(BaseModel):
    """Everything the user knows about themselves, with no presentation decisions.

    It is the source every CV starts from. The LinkedIn importers feed it and the
    user edits it; no CV modifies it.
    """

    schema_version: int = 1
    personal: PersonalInfo
    profile_texts: list[ProfileText] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    courses: list[Course] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    hobbies: list[Hobby] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)

    # Skills you removed by hand. Syncing never deletes, but it cannot give you back what
    # you removed either: without this list, LinkedIn would propose it again.
    dismissed_skills: list[str] = Field(default_factory=list)

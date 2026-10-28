"""Models of a generated CV: the selection recipe and the frozen content.

A CV stores two blocks with different roles, and both are needed:

- `Selection` is the recipe: references by id to what the user chose. It is what
  the history memory reads to propose the same selection in a future
  application.
- `CVContent` is the already resolved result, including this CV's one-off edits.
  It is what guarantees that regenerating the PDF a year from now produces exactly
  the document that was sent to that company.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from cv_generator.models.profile import (
    Course,
    Education,
    Experience,
    Hobby,
    Language,
    PersonalInfo,
    Reference,
    RequiredText,
    Skill,
)
from cv_generator.models.sections import Section
from cv_generator.models.style import Style


class JobPosting(BaseModel):
    """The job application this CV was sent to.

    It is stored next to the snapshot so the history records not only what you sent
    but what you sent it to, and so the CV can be checked again against what the posting asked for.
    """

    company: str | None = None
    url: str | None = None
    text: str = ""


class SelectedExperience(BaseModel):
    """Which experience goes into the CV, and with which of its achievements."""

    id: str
    achievements: list[str] = Field(default_factory=list)


class Selection(BaseModel):
    """The CV recipe: references by id, with no duplicated text.

    In the id lists, the array order is the display order.
    """

    profile_text_id: str | None = None
    header_profession: str | None = None
    # Some applications expect a CV without a photo even if the profile has one. Recipes
    # older than this option do not carry it and are read as "with photo".
    include_photo: bool = True
    # Recipes older than the customization do not carry a style: they are read as "the template's".
    style: Style = Field(default_factory=Style)
    experiences: list[SelectedExperience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    courses: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)


class CVContent(BaseModel):
    """The resolved CV, ready for the template to render."""

    personal: PersonalInfo
    profile: str | None = None
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    courses: list[Course] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    hobbies: list[Hobby] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)


class GeneratedCV(BaseModel):
    """The immutable record of a CV that was already generated and sent."""

    schema_version: int = 1
    cv_id: str = Field(default_factory=lambda: f"cv-{uuid.uuid4().hex[:12]}")
    created: datetime
    cv_name: RequiredText
    target_role: RequiredText
    language: RequiredText
    template: RequiredText
    pdf_file: str
    selection: Selection
    content: CVContent

    # Optional and added after the initial design: CVs generated before this field
    # existed are still read without it.
    posting: JobPosting | None = None

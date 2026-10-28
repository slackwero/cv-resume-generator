"""CV sections: what appears, with which title and in which order.

The title is always customizable. Templates never write literal labels: they
receive `section.title` and print it as is.
"""

from enum import StrEnum

from pydantic import BaseModel

from cv_generator.models.profile import RequiredText


class SectionKind(StrEnum):
    """The content blocks a template can render."""

    PROFILE = "profile"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    LANGUAGES = "languages"
    COURSES = "courses"
    HOBBIES = "hobbies"
    REFERENCES = "references"


class Section(BaseModel):
    """How a section is presented inside one specific CV."""

    kind: SectionKind
    title: RequiredText
    visible: bool = True
    order: int

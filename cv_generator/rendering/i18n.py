"""Labels per language: default section titles and month names.

Only the template labels are translated. The user writes the CV content in whatever
language they want; the application does not translate text.
"""

import re
from pathlib import Path

from pydantic import BaseModel, Field

from cv_generator.models.sections import Section, SectionKind
from cv_generator.storage.repo import read_json

I18N_DIR = Path(__file__).resolve().parents[2] / "i18n"

# Order in which sections appear in a new CV. The user reorders them later in the
# wizard; this is only the starting point.
DEFAULT_ORDER: tuple[SectionKind, ...] = (
    SectionKind.PROFILE,
    SectionKind.EXPERIENCE,
    SectionKind.EDUCATION,
    SectionKind.SKILLS,
    SectionKind.LANGUAGES,
    SectionKind.COURSES,
    SectionKind.HOBBIES,
    SectionKind.REFERENCES,
)


class ContactLabels(BaseModel):
    """The words that precede each contact detail, in the templates that use them."""

    phone: str
    email: str
    website: str
    address: str
    country: str
    age: str


class Translations(BaseModel):
    """The labels of one language, as read from i18n/<code>.json."""

    months: list[str] = Field(min_length=12, max_length=12)
    sections: dict[SectionKind, str]

    # What closes the date range of a current job: "2024-09 — Present".
    present: str
    contact: ContactLabels

    # Words with no value for analyzing a posting: articles, prepositions and the typical
    # filler of a job ad (we are looking for, we offer, experience...).
    stopwords: list[str] = Field(default_factory=list)


# The selector used to show the file stem: the user chose between "es" and "en", not
# between two languages. The code is still the key; this is only how it reads.
LANGUAGE_NAMES = {"es": "Spanish", "en": "English"}


def language_name(code: str) -> str:
    """What a language is called on screen. If it is unknown, its code is shown."""
    return LANGUAGE_NAMES.get(code, code.upper())


def available_languages() -> list[str]:
    """Lists the languages that have a translation file, sorted."""
    return sorted(file.stem for file in I18N_DIR.glob("*.json"))


def load_language(code: str) -> Translations:
    """Loads the labels of a language.

    The code is validated against the list of available languages before touching the
    disk, so a value with path components never gets to open a file outside the
    translations directory.

    Raises:
        ValueError: if the language has no translation file.
    """
    if code not in available_languages():
        raise ValueError(f"unsupported language: {code!r}")

    return Translations.model_validate(read_json(I18N_DIR / f"{code}.json"))


def default_sections(language: str) -> list[Section]:
    """Builds the sections a new CV starts with, titled in its language.

    All of them start visible and numbered from 1. The user then renames the title,
    hides the ones they do not need and reorders them.
    """
    translations = load_language(language)
    return [
        Section(kind=kind, title=translations.sections[kind], order=position)
        for position, kind in enumerate(DEFAULT_ORDER, start=1)
    ]


# Frequent function words. Words that exist in both languages ("a", "no", "en" as an
# English noun) are left out so they do not cancel each other.
FREQUENT_WORDS: dict[str, frozenset[str]] = {
    "es": frozenset(
        {
            "de",
            "la",
            "el",
            "en",
            "y",
            "con",
            "para",
            "los",
            "las",
            "del",
            "por",
            "una",
            "que",
            "se",
            "su",
            "al",
            "como",
            "sus",
            "sobre",
            "desde",
            "entre",
        }
    ),
    "en": frozenset(
        {
            "the",
            "of",
            "and",
            "in",
            "with",
            "for",
            "to",
            "on",
            "as",
            "is",
            "from",
            "by",
            "an",
            "at",
            "across",
            "more",
            "than",
            "including",
            "through",
            "over",
        }
    ),
}

WORD_PATTERN = re.compile(r"[a-záéíóúüñ]+")


def detect_language(text: str, defaults: str = "en") -> str:
    """Guesses which language a text is written in by counting function words.

    It is used for the content imported from LinkedIn: the PDF carries the labels in
    the account's language, which is not necessarily the language the person wrote
    their descriptions in.

    Returns `defaults` if the text is too short to decide.
    """
    words = WORD_PATTERN.findall(text.lower())
    tallies = {
        language: sum(1 for word in words if word in frequent)
        for language, frequent in FREQUENT_WORDS.items()
        if language in available_languages()
    }
    if not tallies:
        return defaults

    winner = max(tallies, key=lambda language: tallies[language])
    return winner if tallies[winner] > 0 else defaults

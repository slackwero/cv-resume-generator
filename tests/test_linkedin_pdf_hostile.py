"""A crafted PDF cannot freeze the backend.

The PDF is a file someone hands you, so its text is input like any other. Reading it
runs in a thread, but a parse that takes minutes still holds the sync screen and the
backend's thread pool. Every matcher of the importer runs in time linear in the line.

Real case 2026-11-08: a study line of 5000 spaces took ~51 s in `STUDY_YEARS_PATTERN`,
whose `.+?\\s*·?\\s*` could split the same spaces in cubic ways; the email, level and
abbreviation patterns, and joining broken lines, were quadratic.
"""

import re
import time

import pytest

from cv_generator.importers.linkedin_pdf import (
    EMAIL_PATTERN,
    LEVEL_PATTERN,
    _ends_in_abbreviation,
    _study_title,
    parse_linkedin_profile,
)

# Far below what the old matchers took with these texts on a laptop (6 to 16 s each),
# far above what a linear parse takes on a slow CI runner.
SECONDS = 2.0

# Each one reaches its matcher: the contact goes before the skills because the sidebar's last
# section lends its tail to the header, and a line of initials that ends in a lowercase one
# is the slow case, the one that does not match.
HOSTILE_TEXTS = {
    "study years": "Education\nUniversity\nTitle" + " " * 3000 + "(",
    "email": "Contact\na@b" + "." * 50_000 + " x\nTop Skills\nKubernetes",
    "language level": "Languages\nEnglish" + " " * 100_000 + "x",
    "company abbreviation": "Experience\n" + "A." * 40_000 + "a.\nRole\nMarch 2021 - Present (1 year)",
    "broken lines": "Education\nUniversity\n" + "a\n" * 600_000,
}


@pytest.mark.parametrize("text", HOSTILE_TEXTS.values(), ids=HOSTILE_TEXTS.keys())
def test_a_hostile_text_is_read_in_linear_time(text: str) -> None:
    start = time.perf_counter()
    parse_linkedin_profile(text)

    assert time.perf_counter() - start < SECONDS


# What each matcher accepted before it was rewritten. The new ones must accept exactly
# the same lines and take the same parts out of them.
OLD_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OLD_LEVEL = re.compile(r"^(?P<value>.+?)\s*\((?P<level>[^()]+)\)$")
OLD_STUDY_YEARS = re.compile(r"^(?P<title>.+?)\s*·?\s*\(\s*\d{4}.*\)$")
OLD_ABBREVIATION = re.compile(r"\b(?:[A-Z]\.){2,}$")

EMAILS = [
    "correo@ejemplo.com",
    "a@b.c",
    "a.b@c.d.e",
    "a@.b.c",
    "a@b.",
    "a@.b",
    "a@b..",
    "a@..b",
    "a@b.c ",
    "@b.c",
    "a@b@c.d",
    "a@bc",
    "a b@c.d",
    "a@b.c\td",
    "ejemplo-123 (LinkedIn)",
]
LEVELS = [
    "Español (Native or Bilingual)",
    "English(Professional)",
    "English  (Professional Working)",
    "Inglés (Elementary) (Limited)",
    "Inglés (Elementary)x",
    "Inglés (Ele(men)tary)",
    "Inglés ()",
    "(Native)",
    "a (b)",
    "a\t(b)",
    "English",
    "C++ (Expert)",
]
STUDIES = [
    "Ingeniería de Sistemas, Computer Engineering · (2006 - 2012)",
    "Title (2010 - 2014)",
    "Title·(2010)",
    "Title · · (2010)",
    "Title\t·\t(2010)",
    "Title (minor) (2010 - 2012)",
    "(2000) Title (2010)",
    "(2010)",
    "Title (2010",
    "Title (201)",
    "Title ( 2010 )",
    "Title (2010) more",
    "Title (abc) (2010) (x)",
    "Bachelor's degree, Business",
]
ABBREVIATIONS = [
    "Banco Agrupado C.A.",
    "Empresa S.A.",
    "S.A.",
    "A.",
    "XA.B.",
    "X A.B.",
    "-A.B.",
    "A.B.C.",
    "xA.B.C.",
    "Corp.",
    "a.b.",
    "Ñ.A.B.",
    "_A.B.",
    "Inc. S.A.",
]


@pytest.mark.parametrize("line", EMAILS)
def test_the_email_matcher_accepts_what_it_did(line: str) -> None:
    assert bool(EMAIL_PATTERN.match(line)) is bool(OLD_EMAIL.match(line))


@pytest.mark.parametrize("line", LEVELS)
def test_the_level_matcher_takes_out_what_it_did(line: str) -> None:
    old, new = OLD_LEVEL.match(line), LEVEL_PATTERN.match(line)

    assert (new and new.group("value", "level")) == (old and old.group("value", "level"))


@pytest.mark.parametrize("line", STUDIES)
def test_the_study_matcher_takes_out_what_it_did(line: str) -> None:
    old = OLD_STUDY_YEARS.match(line)

    assert _study_title(line) == (old and old.group("title").strip(" ·"))


@pytest.mark.parametrize("line", ABBREVIATIONS)
def test_the_abbreviation_matcher_accepts_what_it_did(line: str) -> None:
    assert _ends_in_abbreviation(line) is bool(OLD_ABBREVIATION.search(line))

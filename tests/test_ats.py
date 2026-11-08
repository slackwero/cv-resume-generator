"""The ATS badge is measured, not declared.

An applicant tracking system reads the text extracted from the PDF, never the page as it
looks. A template earns `"ats": true` in its meta.json when every extractor in
`tests/pdf_text.py` gets the CV out of it whole and in order, and when it prints no
photo. The test runs both ways: a template that reads cleanly without the badge fails
too, so the badge always says what was measured.

Real case: `direct` was marked ATS on 2026-10-27 because its HTML was "a single reading
line". The PDF is written in the order the page is drawn, and on 2026-11-07 every
extractor read the headline before the name; one of them read all the section titles
together, ahead of their content.
"""

import itertools
import re
from functools import cache

import pytest

from cv_generator.models.cv import CVContent
from cv_generator.models.profile import Achievement, Course, Education, Experience, Language, Skill
from cv_generator.models.style import Style, StyleFont
from cv_generator.rendering.i18n import default_sections
from cv_generator.rendering.renderer import available_templates, load_meta, render_pdf
from tests.pdf_text import extracted_texts
from tests.test_photo import sample_photo

TEMPLATES = available_templates()

NAME = "Maya Torres"
HEADLINE = "DevSecOps Engineer | Cloud Security"
CONTACT = ("+1 415 555 0100", "maya.torres@example.com", "github.com/mayatorres")
JOBS = [
    ("Northwind Airlines", "Senior DevSecOps Engineer", "Austin, TX", "2022-03", None),
    ("Contoso Consulting", "Cloud Security Engineer", "Remote", "2020-01", "2022-02"),
    ("Fabrikam Bank", "Site Reliability Engineer", "Dallas, TX", "2018-02", "2019-12"),
    ("Tailspin Toys", "Backend Developer", "Austin, TX", "2016-05", "2018-01"),
]
# Multi-word skills next to each other: a parser that gets "Python GitLab CI AWS Security Hub"
# cannot tell where one ends.
SKILLS = ["Kubernetes", "GitLab CI", "AWS Security Hub", "Python", "Terraform"]
# The first thing each section prints, to tell its title stayed with it.
FIRST_CONTENT = {
    "profile": "Engineer who automates security",
    "experience": JOBS[0][1],
    "education": "BSc Computer Science",
    "skills": SKILLS[0],
    "languages": "English",
    "courses": "Certified Kubernetes Administrator",
}


def _achievements(company: str) -> list[Achievement]:
    # With "fi" and "ffi", which some fonts draw as a single ligature that extracts badly.
    return [
        Achievement(
            text=f"Shipped the efficient official workflow number {n} at {company}, "
            f"cutting lead time by {10 * n}% with Terraform and GitLab CI."
        )
        for n in range(1, 6)
    ]


def _content() -> CVContent:
    """A CV with the volume of a real one, over more than one page, with a photo."""
    return CVContent(
        personal={
            "first_name": "Maya",
            "last_name": "Torres",
            "profession": HEADLINE,
            "phone": CONTACT[0],
            "email": CONTACT[1],
            "website": CONTACT[2],
            "address": "Austin, TX",
            "photo": sample_photo(),
        },
        profile="Engineer who automates security in the delivery pipeline: SAST, SCA and secrets in CI/CD.",
        experiences=[
            Experience(
                company=company,
                role=role,
                location=place,
                start=start,
                end=end,
                current=end is None,
                achievements=_achievements(company),
            )
            for company, role, place, start, end in JOBS
        ],
        education=[Education(institution="University of Texas", title="BSc Computer Science")],
        courses=[Course(name="Certified Kubernetes Administrator", institution="CNCF", year=2023)],
        languages=[Language(language="English", level="Professional"), Language(language="Spanish", level="Native")],
        skills=[Skill(name=name) for name in SKILLS],
        sections=[section for section in default_sections("en") if section.kind in FIRST_CONTENT],
    )


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _reading_problems(text: str, sections: list[tuple[str, str]]) -> list[str]:
    """What a parser would get wrong from this text, or nothing.

    `sections` holds each section's title and the first thing it prints, in order.
    """
    lines = [_flat(line) for line in text.splitlines() if line.strip()]
    lower = [line.lower() for line in lines]
    whole = _flat(text)
    problems: list[str] = []

    if not lines or not lines[0].lower().startswith(NAME.lower()):
        problems.append(f"the first line is {lines[0][:40]!r}, not the name" if lines else "no text")

    problems += [
        f"the contact item {item!r} is not a word of its own"
        for item in CONTACT
        if not re.search(r"(?<![\w.+@-])" + re.escape(item) + r"(?![\w@-])", whole)
    ]

    # Each title on a line of its own, in order, with the first thing of its section right after.
    positions = [next((i for i, line in enumerate(lower) if line == title.lower()), None) for title, _ in sections]
    for (title, first), at in zip(sections, positions, strict=True):
        if at is None:
            problems.append(f"the title {title!r} is not on a line of its own")
        elif first.lower() not in " ".join(lower[at + 1 : at + 3]):
            problems.append(f"the title {title!r} is not followed by its content")
    found = [at for at in positions if at is not None]
    if found != sorted(found):
        problems.append("the section titles are out of order")

    # Each role next to its company, as written (CSS can turn it into uppercase), in order.
    last = -1
    for company, role, *_ in JOBS:
        at = next((i for i, line in enumerate(lines) if role in line), None)
        if at is None:
            problems.append(f"the role {role!r} does not come out as written")
            continue
        if company not in " ".join(lines[max(0, at - 1) : at + 3]):
            problems.append(f"the role {role!r} is not next to {company!r}")
        if at < last:
            problems.append(f"the role {role!r} is out of order")
        last = at

    # Every achievement whole and in order.
    previous = -1
    for company, *_ in JOBS:
        for achievement in _achievements(company):
            at = whole.find(achievement.text)
            if at < 0:
                problems.append(f"an achievement comes out broken: {achievement.text[:50]!r}")
            elif at < previous:
                problems.append(f"an achievement is out of order: {achievement.text[:50]!r}")
            previous = max(previous, at)

    # Something between two skills that a parser can split on: a newline or a separator.
    for one, other in itertools.pairwise(SKILLS):
        between = re.search(re.escape(one) + r"([\s|,·;•/]+)" + re.escape(other), text)
        if between is None or not re.search(r"[\n|,·;•/]", between.group(1)):
            problems.append(f"nothing separates {one!r} from {other!r}")
    return problems


@cache
def _problems(slug: str, font: StyleFont | None = None) -> tuple[str, ...]:
    """Everything any extractor gets wrong from this template, rendered once per font."""
    content = _content()
    sections = [(section.title, FIRST_CONTENT[str(section.kind)]) for section in content.sections]
    pdf = render_pdf(content, slug, language="en", style=Style(font=font))
    return tuple(
        f"{extractor}: {problem}"
        for extractor, text in extracted_texts(pdf).items()
        for problem in _reading_problems(text, sections)
    )


@pytest.mark.parametrize("slug", TEMPLATES)
def test_the_ats_badge_is_what_the_parsers_read(slug: str) -> None:
    meta = load_meta(slug)
    problems = list(_problems(slug))
    if meta.supports_photo:
        problems.append("it prints a photo, which adds no text and several filters drop or reject")

    if meta.ats:
        assert problems == [], f"{slug} carries the ATS badge, but:\n" + "\n".join(problems)
    else:
        assert problems, f"{slug} reads cleanly and prints no photo: give it the ATS badge"


@pytest.mark.parametrize("font", list(StyleFont))
@pytest.mark.parametrize("slug", [slug for slug in TEMPLATES if load_meta(slug).ats])
def test_an_ats_template_reads_cleanly_with_every_font(slug: str, font: StyleFont) -> None:
    """The badge holds whatever font the CV picks in the wizard.

    Real case 2026-11-07: with Gill Sans every template came out "T erraform" and
    "Tailspin T oys" in pypdf, from the font's kerning between those letters. And on
    2026-11-08 the same with Modern and Tech on Linux, where DejaVu Sans stands in for
    Avenir Next and Helvetica Neue: the font that draws the CV depends on the computer.
    """
    problems = _problems(slug, font)

    assert problems == (), f"{slug} with {font}:\n" + "\n".join(problems)


def test_the_check_catches_what_broke_direct() -> None:
    """The headline above the name, and the titles read apart from their content."""
    sections = [("Professional Profile", FIRST_CONTENT["profile"]), ("Work Experience", FIRST_CONTENT["experience"])]
    text = "\n".join(["Professional Profile", "Work Experience", HEADLINE, NAME, *CONTACT])

    problems = _reading_problems(text, sections)

    assert any("not the name" in problem for problem in problems)
    assert any("'Professional Profile' is not followed by its content" in problem for problem in problems)

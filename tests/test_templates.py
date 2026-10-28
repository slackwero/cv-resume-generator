"""Contract every template must meet, whatever its design."""

import io
from collections.abc import Iterator
from datetime import date
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from cv_generator.models.cv import CVContent
from cv_generator.models.profile import (
    Achievement,
    Course,
    Education,
    Experience,
    Hobby,
    Language,
    Reference,
    Skill,
)
from cv_generator.models.sections import Section, SectionKind
from cv_generator.models.style import MAX_LINE_HEIGHT, FontSize, PaletteColor, Style, StyleFont
from cv_generator.rendering.i18n import load_language
from cv_generator.rendering.renderer import (
    PROJECT_ROOT,
    TEMPLATES_DIR,
    available_templates,
    load_meta,
    render_html,
    render_pdf,
)
from cv_generator.rendering.styles import PALETTE
from tests.test_models_personal import REQUIRED
from tests.test_photo import sample_photo
from tests.test_template_contrast import _to_rgb, _variables

if TYPE_CHECKING:
    from weasyprint.css import ComputedStyle
    from weasyprint.formatting_structure.boxes import Box

TEMPLATES = available_templates()

# Titles deliberately different from the ones i18n brings: if a template writes its own
# labels instead of using section.title, it shows.
CUSTOM_TITLES = {
    SectionKind.PROFILE: "Who I am",
    SectionKind.EXPERIENCE: "Career",
    SectionKind.EDUCATION: "Training",
    SectionKind.SKILLS: "Stack",
    SectionKind.LANGUAGES: "Tongues",
    SectionKind.COURSES: "Certificates",
    SectionKind.HOBBIES: "Outside work",
    SectionKind.REFERENCES: "Contacts",
}


@pytest.fixture
def content() -> CVContent:
    return CVContent(
        personal={**REQUIRED, "website": "github.com/janedoe", "country": "Spain"},
        profile="Engineer focused on application security.",
        experiences=[
            Experience(
                company="Acme Airlines",
                role="DevSecOps Engineer",
                location="Madrid",
                start="2022-03",
                current=True,
                achievements=[Achievement(text="Cut critical SAST findings by 80%.")],
            ),
            Experience(
                company="Previous Consulting",
                role="Backend Developer",
                start="2019-01",
                end="2022-02",
                achievements=[Achievement(text="Built the payments API.")],
            ),
        ],
        education=[Education(institution="Example University", title="Civil Engineering")],
        courses=[Course(name="CKA", institution="CNCF", year=2023)],
        languages=[Language(language="Spanish", level="Native")],
        skills=[Skill(name="Kubernetes"), Skill(name="Python")],
        hobbies=[Hobby(text="Cycling")],
        references=[Reference(name="Reference Person", relationship="Direct manager")],
        sections=[
            Section(kind=kind, title=title, order=position)
            for position, (kind, title) in enumerate(CUSTOM_TITLES.items(), start=1)
        ],
    )


def test_templates_are_installed() -> None:
    """Without this, a broken discovery would leave the tests below with no cases and green.

    How many is not pinned: the catalog was deliberately trimmed to a few well
    differentiated ones, and adding or removing a template is adding or removing a folder.
    """
    assert TEMPLATES
    assert len(TEMPLATES) == len(list(TEMPLATES_DIR.glob("*/meta.json")))


@pytest.mark.parametrize("slug", TEMPLATES)
def test_the_template_describes_itself(slug: str) -> None:
    meta = load_meta(slug)

    assert meta.name.strip() != ""
    assert meta.description.strip() != ""
    assert set(meta.supported_sections) == set(SectionKind), "it must declare every section"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_prints_the_titles_the_user_customized(slug: str, content: CVContent) -> None:
    html = render_html(content, slug, language="es")

    for title in CUSTOM_TITLES.values():
        assert title in html, f"{slug} does not print the custom title '{title}'"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_writes_no_labels_of_its_own(slug: str, content: CVContent) -> None:
    html = render_html(content, slug, language="es")
    defaults = load_language("es").sections

    for kind, caption in defaults.items():
        assert caption not in html, f"{slug} writes the label '{caption}' of {kind} instead of using section.title"


@pytest.mark.parametrize("slug", TEMPLATES)
@pytest.mark.parametrize(("language", "present"), [("es", "actualidad"), ("en", "Present")])
def test_a_current_job_says_it_is_current_in_the_cv_language(
    slug: str, language: str, present: str, content: CVContent
) -> None:
    """An open range ("2022-03 —") does not tell a current job apart from a missing date."""
    html = render_html(content, slug, language=language)

    assert f"2022-03 — {present}" in html
    assert "2019-01 — 2022-02" in html, "a closed job keeps both of its dates"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_shows_the_required_data(slug: str, content: CVContent) -> None:
    html = render_html(content, slug, language="es")

    assert content.personal.first_name in html
    assert content.personal.last_name in html
    assert content.personal.email in html
    assert content.personal.phone in html


@pytest.mark.parametrize("slug", TEMPLATES)
def test_includes_the_content_of_every_section(slug: str, content: CVContent) -> None:
    html = render_html(content, slug, language="es")

    for expected in [
        "Cut critical SAST findings by 80%.",
        "Acme Airlines",
        "Example University",
        "Kubernetes",
        "Spanish",
        "CKA",
        "Cycling",
        "Reference Person",
    ]:
        assert expected in html, f"{slug} does not show '{expected}'"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_escapes_user_content(slug: str, content: CVContent) -> None:
    content.experiences[0].achievements[0].text = "<script>alert('xss')</script>"

    html = render_html(content, slug, language="es")

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("slug", TEMPLATES)
def test_omits_hidden_sections(slug: str, content: CVContent) -> None:
    content.sections = [s for s in content.sections if s.kind is not SectionKind.HOBBIES]

    html = render_html(content, slug, language="es")

    assert "Outside work" not in html
    assert "Cycling" not in html, f"{slug} shows the content of a section that was not included"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_respects_the_section_order(slug: str, content: CVContent) -> None:
    html = render_html(content, slug, language="es")

    assert html.index("Career") < html.index("Training") < html.index("Stack")


@pytest.mark.parametrize("slug", TEMPLATES)
def test_produces_a_readable_pdf(slug: str, content: CVContent) -> None:
    pdf = render_pdf(content, slug, today=date(2026, 8, 27), language="es")

    assert pdf.startswith(b"%PDF-")
    # In uppercase: a template may apply text-transform and that is valid.
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages).upper()
    assert "JANE" in text
    assert "CAREER" in text


@pytest.mark.parametrize("slug", TEMPLATES)
@pytest.mark.parametrize("font", [None, *StyleFont])
def test_the_pdf_text_is_readable_by_an_ats(slug: str, font: StyleFont | None, content: CVContent) -> None:
    """Automated filters read the extracted text, not the rendered page.

    A high letter-spacing makes the extractor return "C A R E E R": the CV looks
    flawless and still no ATS recognizes the section or the keywords. That is why the
    contract requires every title and every piece of data to come out whole. It is
    repeated with each font because the spacing one tolerates can split the words of
    another.
    """
    pdf = render_pdf(content, slug, today=date(2026, 8, 27), language="es", style=Style(font=font))
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages).upper()

    for title in CUSTOM_TITLES.values():
        assert title.upper() in text, f"{slug} with {font} splits '{title}' when extracting the PDF text"

    for piece in ["JANE", "DOE", "ACME AIRLINES", "KUBERNETES", "SAST"]:
        assert piece in text, f"{slug} with {font} splits '{piece}' when extracting the PDF text"


@pytest.fixture
def long_content(content: CVContent) -> CVContent:
    """A CV with the volume of a real one, which forces pagination."""
    content.experiences = [
        Experience(
            company=f"Company {number}",
            role=f"Cargo {number}",
            start="2015-01",
            end="2018-12",
            achievements=[
                Achievement(
                    text=f"Achievement {index} of job {number}, with enough text "
                    f"to take more than one line in any template."
                )
                for index in range(5)
            ],
        )
        for number in range(7)
    ]
    return content


@pytest.mark.parametrize("slug", TEMPLATES)
def test_does_not_waste_the_first_page(slug: str, long_content: CVContent) -> None:
    """The first page must carry content, not only the header.

    A badly solved column layout pushes the whole body to the next page: the PDF is
    generated, the text is complete and still the CV is useless because the first page
    is left blank. The text presence tests do not see it.
    """
    pdf = render_pdf(long_content, slug, today=date(2026, 8, 27), language="es")

    _require_experience_on_first_page(slug, pdf)


# An achievement like the ones in the real profile: two or three lines per bullet, not half of one.
LONG_ACHIEVEMENT_TEXT = (
    "Designed and rolled out the security of the delivery chain: static analysis, "
    "dependencies and secrets on every merge request, with the exceptions approved by the "
    "owning team and followed up until closed, which brought the mean time to remediation "
    "down from several weeks to a few days."
)


@pytest.fixture
def content_with_long_first_job(long_content: CVContent) -> CVContent:
    """The first job like the one in the real profile: ten achievements of about 280 characters.

    With five short achievements each entry fit in the rest of page 1 even if it could not
    be split, and the test passed while the real CV, with large text, left page 1 with only
    the header and the profile.
    """
    long_content.profile = " ".join([LONG_ACHIEVEMENT_TEXT] * 2)
    long_content.experiences[0].achievements = [
        Achievement(text=f"Achievement {index} of job 0. {LONG_ACHIEVEMENT_TEXT}") for index in range(10)
    ]
    return long_content


@pytest.mark.parametrize("slug", TEMPLATES)
def test_does_not_waste_the_first_page_at_the_extreme(slug: str, content_with_long_first_job: CVContent) -> None:
    """Large text with the maximum line height is what pushes the body down the most: if even
    then the work history starts on page 1, it does with any other style too.
    """
    style = Style(size=FontSize.LARGE, line_height=MAX_LINE_HEIGHT)

    pdf = render_pdf(content_with_long_first_job, slug, today=date(2026, 8, 27), language="es", style=style)

    _require_experience_on_first_page(slug, pdf)


def test_sidebar_keeps_its_bar_at_the_extreme(content_with_long_first_job: CVContent) -> None:
    """With large text, line height 2.0, the photo and the skills of a real profile, the bar
    does not fit on page 1: it has to continue on page 2, not be cut where the sheet ends.

    It looks at the end of the bar, the last skill and the last hobby: if the grid stopped
    splitting it across pages, that is the first thing that would be lost.
    """
    content = content_with_long_first_job
    content.personal.photo = sample_photo()
    content.skills = [Skill(name=f"Tool {number}") for number in range(28)]
    style = Style(size=FontSize.LARGE, line_height=MAX_LINE_HEIGHT)

    pdf = render_pdf(content, "sidebar", today=date(2026, 8, 27), language="es", style=style)

    text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "Tool 27" in text, "the bar loses the last skills"
    assert "Cycling" in text, "the bar loses its last section"


def _require_experience_on_first_page(slug: str, pdf: bytes) -> None:
    first_one = (PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or "").upper()

    assert "CAREER" in first_one, f"{slug} leaves the work history section off page 1"
    assert "ACHIEVEMENT 0 OF JOB 0" in first_one, f"{slug} shows no achievement on page 1"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_draws_the_photo_only_if_it_declares_support(slug: str, content: CVContent) -> None:
    """`supports_photo` decides whether the wizard offers the photo and whether the snapshot keeps it.

    If the meta.json said one thing and the CSS did another, the user would check "include
    photo" and the PDF would come out without it, or the history would keep a photo that
    was never sent.
    """
    content.personal.photo = sample_photo()

    pdf = render_pdf(content, slug, today=date(2026, 8, 27), language="es")
    images = [image for page in PdfReader(io.BytesIO(pdf)).pages for image in page.images]

    assert bool(images) is load_meta(slug).supports_photo


@pytest.mark.parametrize(("language", "caption"), [("es", "Teléfono"), ("en", "Phone")])
def test_sidebar_labels_the_contact_in_the_cv_language(language: str, caption: str, content: CVContent) -> None:
    html = render_html(content, "sidebar", language=language)

    assert caption in html


@pytest.mark.parametrize("slug", TEMPLATES)
def test_an_ats_template_has_no_photo(slug: str) -> None:
    """The wizard's ATS badge promises a CV an automated filter reads whole: a photo adds no
    text and several filters drop it or reject the document."""
    meta = load_meta(slug)

    if meta.ats:
        assert not meta.supports_photo


def test_there_is_at_least_one_ats_template() -> None:
    """Without this, the test above would pass vacuously if nobody declared `ats`."""
    assert any(load_meta(slug).ats for slug in TEMPLATES)


def test_marks_the_experiences_that_have_a_place(content: CVContent) -> None:
    """A template that puts the place together with the dates needs to know whether there is
    a place: without one, the dates cannot go after a separator with nothing to separate."""
    html = render_html(content, "direct", language="es")

    # With the attribute's closing quote: the embedded CSS also names the class.
    assert html.count('entry--with-place"') == 1, "only the first experience has a location"


def test_direct_puts_place_and_dates_on_the_same_line(content: CVContent) -> None:
    pdf = render_pdf(content, "direct", today=date(2026, 8, 27), language="es")
    lines = (PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or "").upper().splitlines()

    with_place = next(line for line in lines if "MADRID" in line)
    assert "2022-03" in with_place, f"the place and the dates ended up apart: {with_place!r}"

    without_place = next(line for line in lines if "PREVIOUS CONSULTING" in line)
    assert "2019-01" not in without_place, f"without a place, the dates must go on their own line: {without_place!r}"


# --- Customization ---------------------------------------------------------------------
#
# The CV style does not rewrite the template: it appends a `:root` that overrides its
# variables. That is why a template is only customizable if it declares them and uses
# them in what is drawn; these tests read it from the render, not from the CSS.

REQUIRED_VARIABLES = {
    "--accent",
    "--heading-font",
    "--body-font",
    "--scale",
    "--line-height",
    "--entry-break",
    "--break-after-header",
}


def _css_of(slug: str) -> str:
    return (TEMPLATES_DIR / slug / "styles.css").read_text(encoding="utf-8")


def _walk(box: "Box") -> Iterator[tuple[set[str], "ComputedStyle"]]:
    element = box.element
    css_classes = set((element.get("class") or "").split()) if element is not None else set()
    yield css_classes, box.style
    for child in getattr(box, "children", []):
        yield from _walk(child)


def _boxes(html: str) -> Iterator[tuple[set[str], "ComputedStyle"]]:
    """Every box of the paginated document, with its element's classes and its computed style.

    It is the style after resolving `var()` and `calc()`: what is really drawn.
    """
    from weasyprint import HTML

    for page in HTML(string=html, base_url=str(PROJECT_ROOT)).render().pages:
        yield from _walk(page._page_box)


def _computed_colors(html: str) -> set[tuple[int, int, int]]:
    """The text and background colors of every box, as 0-255 integers."""
    return {
        tuple(round(channel * 255) for channel in color.to("srgb").coordinates)
        for _, style in _boxes(html)
        for color in (style["color"], style["background_color"])
        if color.alpha > 0
    }


def _family(html: str, css_class: str) -> str:
    """The chosen family (the first in the stack) of the first element with that class."""
    return next(style["font_family"][0] for css_classes, style in _boxes(html) if css_class in css_classes)


@pytest.mark.parametrize("slug", TEMPLATES)
def test_the_template_declares_the_style_variables(slug: str) -> None:
    """Without these variables the style selector writes a `:root` nobody reads.

    `--scale` at 1 leaves every size as it was. `--line-height` has to be the meta.json
    one because the wizard shows that value as the template's and starts from it when
    pressing - or +: if the CSS used another, the control would lie.
    """
    variables = _variables(_css_of(slug))

    assert REQUIRED_VARIABLES <= set(variables), f"{slug} is missing {REQUIRED_VARIABLES - set(variables)}"
    assert variables["--scale"] == "1"
    assert float(variables["--line-height"]) == load_meta(slug).line_height
    # Uncustomized, it paginates like the CVs already generated: the entry is not split, and
    # the header is not tied to its first achievement (tying it moved a break in a history CV).
    assert variables["--entry-break"] == "avoid"
    assert variables["--break-after-header"] == "auto"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_changing_the_color_changes_what_is_drawn(slug: str, content: CVContent) -> None:
    red = _to_rgb(PALETTE[PaletteColor.RED].accent)

    assert red not in _computed_colors(render_html(content, slug, language="es"))
    assert red in _computed_colors(render_html(content, slug, language="es", style=Style(color=PaletteColor.RED))), (
        f"{slug} paints nothing with --accent"
    )


@pytest.mark.parametrize("slug", TEMPLATES)
def test_changing_the_font_changes_the_name_and_the_body(slug: str, content: CVContent) -> None:
    """Elegant (Baskerville) is no template's own font: seeing it is seeing it change."""
    html = render_html(content, slug, language="es", style=Style(font=StyleFont.ELEGANT))

    assert _family(html, "header__name") == "Baskerville"
    assert _family(html, "achievements") == "Baskerville"


@pytest.mark.parametrize("slug", TEMPLATES)
def test_with_large_text_the_entry_splits_and_the_header_stays_with_its_achievement(
    slug: str, content: CVContent
) -> None:
    """They read it from the paginated document: a `var()` WeasyPrint did not resolve in a
    break property would fall back to `auto` without warning, and the CVs already generated
    would paginate differently."""

    def cuts(style: Style | None) -> tuple[str, str]:
        boxes = list(_boxes(render_html(content, slug, language="es", style=style)))
        entry = next(computed["break_inside"] for css_classes, computed in boxes if "entry" in css_classes)
        header = next(computed["break_after"] for css_classes, computed in boxes if "entry__header" in css_classes)
        return entry, header

    assert cuts(None) == ("avoid", "auto")
    assert cuts(Style(size=FontSize.LARGE)) == ("auto", "avoid")


def test_technical_keeps_the_monospace_with_any_font(content: CVContent) -> None:
    """The data monospace is what makes `technical` recognizable; the font selector does not
    touch it because it lives in `--data-font`, outside the contract."""
    html = render_html(content, "technical", language="es", style=Style(font=StyleFont.ELEGANT))

    assert _family(html, "entry__dates") == "SFMono-Regular"
    assert _family(html, "section__title") == "SFMono-Regular"

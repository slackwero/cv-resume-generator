import io
from datetime import date

import pytest
from pypdf import PdfReader

from cv_generator.models.cv import CVContent
from cv_generator.models.profile import Achievement, Experience, Skill
from cv_generator.models.sections import Section, SectionKind
from cv_generator.models.style import PaletteColor, Style
from cv_generator.rendering.renderer import (
    available_templates,
    load_meta,
    render_html,
    render_pdf,
)
from cv_generator.rendering.styles import PALETTE
from tests.test_models_personal import REQUIRED


@pytest.fixture
def content() -> CVContent:
    return CVContent(
        personal=REQUIRED,
        profile="Application security specialist.",
        experiences=[
            Experience(
                company="Acme Airlines",
                role="DevSecOps Engineer",
                start="2022-03",
                current=True,
                achievements=[Achievement(text="Cut critical SAST findings by 80%.")],
            )
        ],
        skills=[Skill(name="Kubernetes")],
        sections=[
            Section(kind=SectionKind.PROFILE, title="About me", order=1),
            Section(kind=SectionKind.EXPERIENCE, title="Career", order=2),
            Section(kind=SectionKind.SKILLS, title="Stack", order=3),
        ],
    )


def test_there_is_at_least_one_installed_template() -> None:
    assert "modern" in available_templates()


def test_the_meta_describes_the_template() -> None:
    meta = load_meta("modern")

    assert meta.name
    assert SectionKind.EXPERIENCE in meta.supported_sections


@pytest.mark.parametrize("malicious_slug", ["../secrets", "modern/../../etc", "/etc/passwd"])
def test_rejects_template_slugs_pointing_outside_the_directory(malicious_slug: str) -> None:
    with pytest.raises(ValueError, match="template not found"):
        load_meta(malicious_slug)


def test_html_shows_the_name_and_profession(content: CVContent) -> None:
    html = render_html(content, "modern", language="es")

    assert "Jane" in html
    assert "DevSecOps Engineer" in html


def test_html_uses_each_section_custom_title(content: CVContent) -> None:
    html = render_html(content, "modern", language="es")

    assert "Career" in html
    assert "Experiencia laboral" not in html, "the template must not write labels of its own"


def test_html_respects_the_section_order(content: CVContent) -> None:
    html = render_html(content, "modern", language="es")

    assert html.index("About me") < html.index("Career") < html.index("Stack")


def test_html_includes_the_selected_achievements(content: CVContent) -> None:
    html = render_html(content, "modern", language="es")

    assert "Cut critical SAST findings by 80%." in html


def test_html_omits_a_section_that_was_not_included(content: CVContent) -> None:
    html = render_html(content, "modern", language="es")

    assert "References" not in html


def test_escapes_user_content_instead_of_interpreting_it(content: CVContent) -> None:
    content.experiences[0].achievements[0].text = "<script>alert('xss')</script>"

    html = render_html(content, "modern", language="es")

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def _pdf_text(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_produces_a_valid_pdf_file(content: CVContent) -> None:
    pdf = render_pdf(content, "modern", language="es")

    assert pdf.startswith(b"%PDF-")


def test_the_pdf_contains_the_cv_data(content: CVContent) -> None:
    text = _pdf_text(render_pdf(content, "modern", language="es"))

    assert "Jane" in text
    assert "DevSecOps Engineer" in text
    assert "Cut critical SAST findings by 80%." in text


def test_the_pdf_uses_the_custom_section_titles(content: CVContent) -> None:
    text = _pdf_text(render_pdf(content, "modern", language="es"))

    assert "CAREER" in text.upper()
    assert "EXPERIENCIA LABORAL" not in text.upper()


def test_regenerating_the_same_content_produces_the_same_document(content: CVContent) -> None:
    first = _pdf_text(render_pdf(content, "modern", today=date(2026, 8, 27), language="es"))
    second_one = _pdf_text(render_pdf(content, "modern", today=date(2026, 8, 27), language="es"))

    assert first == second_one


def test_age_is_frozen_with_the_given_date(content: CVContent) -> None:
    content.personal.birth_date = date(1990, 3, 15)

    in_2026 = _pdf_text(render_pdf(content, "modern", today=date(2026, 8, 27), language="es"))
    in_2030 = _pdf_text(render_pdf(content, "modern", today=date(2030, 8, 27), language="es"))

    assert "36" in in_2026
    assert "40" in in_2030


def test_without_style_the_css_is_the_template_one(content: CVContent) -> None:
    base = render_html(content, "modern", language="es")
    assert render_html(content, "modern", language="es", style=Style()) == base
    red = render_html(content, "modern", language="es", style=Style(color=PaletteColor.RED))
    assert PALETTE[PaletteColor.RED].accent in red

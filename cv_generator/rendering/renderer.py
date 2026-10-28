"""Rendering of a CV: from the resolved content to a template's HTML.

The HTML `render_html` produces is exactly what is later converted to PDF, and the
same one the interface shows in the preview. Without that single source, what the
user sees would not be what they export.
"""

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from cv_generator.models.cv import CVContent
from cv_generator.models.sections import SectionKind
from cv_generator.models.style import Style
from cv_generator.native_libs import prepare_native_libraries
from cv_generator.rendering.i18n import load_language
from cv_generator.rendering.styles import css_for_style
from cv_generator.storage.repo import read_json

if TYPE_CHECKING:
    from weasyprint import HTML

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "templates"


class TemplateMeta(BaseModel):
    """What a template declares about itself in its meta.json."""

    slug: str
    name: str
    description: str
    supports_photo: bool = False
    # Meant for an automated filter to read it whole: a single reading line, real text and
    # no photo. The wizard marks it with a badge in the carousel.
    ats: bool = False
    line_height: float
    supported_sections: list[SectionKind]


def available_templates() -> list[str]:
    """Lists the slugs of the installed templates.

    A template is a folder in templates/ that has a meta.json: adding a template is
    adding a folder, without touching code.
    """
    if not TEMPLATES_DIR.is_dir():
        return []

    return sorted(folder.name for folder in TEMPLATES_DIR.iterdir() if (folder / "meta.json").is_file())


def load_meta(slug: str) -> TemplateMeta:
    """Reads a template's description.

    The slug is validated against the installed templates before touching the disk,
    so a value with path components never opens a file outside the templates
    directory.

    Raises:
        ValueError: if there is no template with that slug.
    """
    if slug not in available_templates():
        raise ValueError(f"template not found: {slug!r}")

    data = read_json(TEMPLATES_DIR / slug / "meta.json")
    return TemplateMeta.model_validate({**data, "slug": slug})


def _build_environment() -> Environment:
    """Jinja2 environment with autoescape on.

    Autoescape is what prevents the user's text (an achievement, a description) from
    being interpreted as HTML when rendering.
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(default_for_string=True, default=True),
    )


def render_html(
    content: CVContent, slug: str, today: date | None = None, *, language: str, style: Style | None = None
) -> str:
    """Renders the CV as a self-contained HTML document, with the CSS embedded.

    Args:
        content: the CV already resolved against the master profile.
        slug: the template to use.
        today: date used to compute the age. When regenerating a history CV, pass its
            creation date, or the age shown would change over time and the document
            would no longer be identical to the one that was sent.
        language: the language of the CV labels. Templates only write words of their
            own in two places: the one that closes the date range of a current job, and
            the contact labels, in the templates that label it.
        style: what the CV customizes in the template. It is appended at the end of the
            template's CSS; `None` or empty leave the HTML exactly as the template
            produces it.
    """
    load_meta(slug)

    directory = TEMPLATES_DIR / slug
    template = _build_environment().get_template(f"{slug}/template.html")
    translations = load_language(language)

    css = (directory / "styles.css").read_text(encoding="utf-8")
    if style is not None and not style.empty:
        css = css + "\n" + css_for_style(style)

    return template.render(
        cv=content,
        css=css,
        age=content.personal.compute_age(today or date.today()),
        present=translations.present,
        captions=translations.contact,
    )


def _load_weasyprint() -> type["HTML"]:
    """Imports WeasyPrint lazily, with a useful message if the native environment is missing."""
    prepare_native_libraries()
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "WeasyPrint could not load its native libraries. On macOS they are installed with: "
            "brew install pango cairo gdk-pixbuf libffi"
        ) from exc
    return HTML


def render_pdf_and_pages(
    content: CVContent, slug: str, today: date | None = None, *, language: str, style: Style | None = None
) -> tuple[bytes, int]:
    """Renders the PDF and also returns how many pages it takes.

    "How many pages, and where does it break" is the only question a CV raises, and only
    WeasyPrint's paginator can answer it: the HTML flows continuously. It paginates
    once, and both the bytes and the count come from that same document.

    Raises:
        RuntimeError: if WeasyPrint cannot load its native libraries.
    """
    html = render_html(content, slug, today, language=language, style=style)
    document = _load_weasyprint()(string=html, base_url=str(PROJECT_ROOT)).render()
    return document.write_pdf(), len(document.pages)


def render_pdf(
    content: CVContent, slug: str, today: date | None = None, *, language: str, style: Style | None = None
) -> bytes:
    """Renders the CV to PDF from the same HTML the preview shows.

    Args:
        content: the CV already resolved against the master profile.
        slug: the template to use.
        today: date used to compute the age. When regenerating a history CV, pass its
            creation date to get the same document.
        language: the language of the CV labels.
        style: the CV customization; `None` uses the template as is.
    """
    return render_pdf_and_pages(content, slug, today, language=language, style=style)[0]

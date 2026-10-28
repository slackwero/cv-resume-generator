"""Builds the file name of the generated CVs.

Format: <initials>-<role>-<month><year>.pdf  ->  jd-devsecops-march2026.pdf
"""

import re
from datetime import date
from pathlib import Path

from cv_generator.rendering.i18n import load_language
from cv_generator.text import strip_accents


def slugify(text: str) -> str:
    """Turns free text into a fragment that is safe for a file name."""
    without_accents = strip_accents(text).lower()
    alphanumeric_only = re.sub(r"[^a-z0-9]+", "-", without_accents)
    return alphanumeric_only.strip("-")


def build_initials(first_name: str, last_name: str) -> str:
    """Takes the first letter of the first name and of the last name, lowercase and without accents."""
    return slugify(first_name[:1]) + slugify(last_name[:1])


def build_filename(
    first_name: str,
    last_name: str,
    role: str,
    on_date: date,
    language: str,
) -> str:
    """Builds the PDF name from the CV data.

    The month is written in the CV language, taken from the i18n labels.
    """
    initials = build_initials(first_name, last_name)
    month = load_language(language).months[on_date.month - 1]
    return f"{initials}-{slugify(role)}-{month}{on_date.year}.pdf"


def _validate_simple_name(name: str) -> None:
    """Requires the name to be a bare file, with no path components."""
    if not name or name != Path(name).name:
        raise ValueError(f"invalid file name: {name!r}")


def resolve_available_path(directory: Path, name: str) -> Path:
    """Returns a free path inside the directory, without overwriting existing files.

    If the name is already taken it adds an incremental suffix: -2, -3, etc.

    Raises:
        ValueError: if the name is not a simple file (it contains separators, ".."
            components or is an absolute path), which would allow writing outside the
            output directory.
    """
    _validate_simple_name(name)
    path = directory / name
    if not path.exists():
        return path

    counter = 2
    while (candidate := directory / f"{path.stem}-{counter}{path.suffix}").exists():
        counter += 1
    return candidate

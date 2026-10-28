from datetime import date
from pathlib import Path

import pytest

from cv_generator.rendering.filename import build_filename, resolve_available_path


def test_builds_initials_role_and_month_in_spanish() -> None:
    result = build_filename(
        first_name="Jane",
        last_name="Doe",
        role="DevSecOps",
        on_date=date(2026, 3, 15),
        language="es",
    )

    assert result == "jd-devsecops-marzo2026.pdf"


def test_uses_the_month_in_the_cv_language() -> None:
    result = build_filename(
        first_name="Jane",
        last_name="Doe",
        role="DevSecOps",
        on_date=date(2026, 3, 15),
        language="en",
    )

    assert result == "jd-devsecops-march2026.pdf"


def test_returns_the_path_as_is_if_it_does_not_exist(tmp_path: Path) -> None:
    path = resolve_available_path(tmp_path, "jd-devsecops-marzo2026.pdf")

    assert path == tmp_path / "jd-devsecops-marzo2026.pdf"


def test_adds_numeric_suffix_when_file_exists(tmp_path: Path) -> None:
    (tmp_path / "jd-devsecops-marzo2026.pdf").write_bytes(b"pdf existing")
    (tmp_path / "jd-devsecops-marzo2026-2.pdf").write_bytes(b"pdf existing")

    path = resolve_available_path(tmp_path, "jd-devsecops-marzo2026.pdf")

    assert path == tmp_path / "jd-devsecops-marzo2026-3.pdf"


def test_does_not_overwrite_the_original_file(tmp_path: Path) -> None:
    original = tmp_path / "jd-devsecops-marzo2026.pdf"
    original.write_bytes(b"contenido original")

    resolve_available_path(tmp_path, "jd-devsecops-marzo2026.pdf")

    assert original.read_bytes() == b"contenido original"


@pytest.mark.parametrize(
    "malicious_name",
    ["../outside.pdf", "../../etc/passwd", "sub/dir/cv.pdf", "/absolute.pdf"],
)
def test_rejects_names_that_escape_the_directory(tmp_path: Path, malicious_name: str) -> None:
    with pytest.raises(ValueError, match="invalid file name"):
        resolve_available_path(tmp_path, malicious_name)


def test_normalizes_accents_and_spaces_in_the_role() -> None:
    result = build_filename(
        first_name="Álvaro",
        last_name="Núñez",
        role="Analista de Programación Señor",
        on_date=date(2026, 12, 1),
        language="es",
    )

    assert result == "an-analista-de-programacion-senor-diciembre2026.pdf"

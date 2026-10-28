from pathlib import Path

import pytest

from cv_generator.services.system import open_with_viewer


def test_rejects_a_file_outside_the_allowed_directory(tmp_path: Path) -> None:
    allowed = tmp_path / "output"
    allowed.mkdir()
    intruder = tmp_path / "secreto.pdf"
    intruder.write_bytes(b"%PDF-")

    with pytest.raises(ValueError, match="outside the allowed directory"):
        open_with_viewer(intruder, allowed)


def test_rejects_a_path_that_escapes_with_dots(tmp_path: Path) -> None:
    allowed = tmp_path / "output"
    allowed.mkdir()

    with pytest.raises(ValueError, match="outside the allowed directory"):
        open_with_viewer(allowed / ".." / "other.pdf", allowed)


def test_rejects_a_missing_file(tmp_path: Path) -> None:
    allowed = tmp_path / "output"
    allowed.mkdir()

    with pytest.raises(FileNotFoundError):
        open_with_viewer(allowed / "missing.pdf", allowed)

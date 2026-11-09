from pathlib import Path

import pytest

from cv_generator.services import system
from cv_generator.services.system import ViewerUnavailable, open_with_viewer


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


@pytest.mark.parametrize("name", ["cv.command", "cv.app", "cv.pdf.sh", "cv"])
def test_rejects_a_file_that_is_not_a_pdf(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The path arrives from the browser, and `open` runs a .command file in the Terminal."""
    opened = tmp_path / name
    opened.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(system.subprocess, "run", lambda *a, **k: pytest.fail("the viewer was started"))

    with pytest.raises(ValueError, match="not a PDF"):
        open_with_viewer(opened, tmp_path, platform="darwin")


def _pdf(folder: Path) -> Path:
    pdf = folder / "cv.pdf"
    pdf.write_bytes(b"%PDF-")
    return pdf


def test_windows_opens_the_file_with_its_associated_viewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = _pdf(tmp_path)
    opened: list[Path] = []
    monkeypatch.setattr(system.os, "startfile", opened.append, raising=False)
    monkeypatch.setattr(system.subprocess, "run", lambda *a, **k: pytest.fail("no subprocess on Windows"))

    open_with_viewer(pdf, tmp_path, platform="win32")

    assert opened == [pdf.resolve()]


def test_macos_opens_with_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = _pdf(tmp_path)
    calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(system.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))

    open_with_viewer(pdf, tmp_path, platform="darwin")

    assert calls == [(["/usr/bin/open", str(pdf.resolve())], {"check": False})]


def test_a_viewer_that_cannot_start_is_not_a_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = _pdf(tmp_path)

    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(system.subprocess, "run", missing)

    with pytest.raises(ViewerUnavailable) as raised:
        open_with_viewer(pdf, tmp_path, platform="linux")

    assert not isinstance(raised.value, FileNotFoundError)
    assert isinstance(raised.value.__cause__, FileNotFoundError)


def test_windows_without_an_associated_viewer_is_viewer_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = _pdf(tmp_path)

    def no_association(path: Path) -> None:
        raise OSError(1155, "No application is associated")

    monkeypatch.setattr(system.os, "startfile", no_association, raising=False)

    with pytest.raises(ViewerUnavailable):
        open_with_viewer(pdf, tmp_path, platform="win32")

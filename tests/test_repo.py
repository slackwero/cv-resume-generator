from pathlib import Path

import pytest

from cv_generator.storage.repo import read_json, save_json


def test_saves_and_reads_the_same_content(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    data = {"first_name": "Jane", "last_name": "Doe", "years": 12}

    save_json(path, data)

    assert read_json(path) == data


def test_keeps_accents_without_escaping_them(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"

    save_json(path, {"profession": "Ingeniero de Programación"})

    assert "Programación" in path.read_text(encoding="utf-8")


def _break_write_midway(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates a full disk: writes half of the content and raises OSError."""
    real_write = Path.write_text

    def failing_write(self: Path, content: str, **kwargs: object) -> int:
        real_write(self, content[: len(content) // 2], **kwargs)
        raise OSError("no space left on device")

    monkeypatch.setattr(Path, "write_text", failing_write)


def test_a_write_failure_does_not_corrupt_the_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profile.json"
    save_json(path, {"first_name": "Jane"})
    _break_write_midway(monkeypatch)

    with pytest.raises(OSError, match="space"):
        save_json(path, {"first_name": "Jane", "profession": "DevSecOps", "country": "Spain"})

    monkeypatch.undo()
    assert read_json(path) == {"first_name": "Jane"}


def test_leaves_no_temp_files_after_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profile.json"
    save_json(path, {"first_name": "Jane"})
    _break_write_midway(monkeypatch)

    with pytest.raises(OSError, match="space"):
        save_json(path, {"first_name": "Jane", "profession": "DevSecOps", "country": "Spain"})

    monkeypatch.undo()
    assert list(tmp_path.iterdir()) == [path]

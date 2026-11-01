import errno
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from cv_generator.storage import repo
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


def _fail_replace(monkeypatch: pytest.MonkeyPatch, errors: list[OSError]) -> tuple[list[float], list[int]]:
    """Makes os.replace raise the given errors in order, then work. Returns (waits, calls)."""
    waits: list[float] = []
    calls: list[int] = []
    pending = list(errors)

    def flaky_replace(src: Path, dst: Path) -> None:
        calls.append(1)
        if pending:
            raise pending.pop(0)
        os.replace(src, dst)

    monkeypatch.setattr(repo, "os", SimpleNamespace(replace=flaky_replace))
    monkeypatch.setattr(repo, "_sleep", waits.append)
    return waits, calls


def test_waits_out_a_brief_lock_on_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profile.json"
    save_json(path, {"first_name": "Jane"})
    waits, calls = _fail_replace(monkeypatch, [PermissionError("locked"), PermissionError("locked")])

    save_json(path, {"first_name": "John"})

    assert read_json(path) == {"first_name": "John"}
    assert len(calls) == 3
    assert waits == [0.05, 0.1]
    assert list(tmp_path.iterdir()) == [path]


def test_gives_up_after_five_attempts_and_leaves_no_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profile.json"
    save_json(path, {"first_name": "Jane"})
    waits, calls = _fail_replace(monkeypatch, [PermissionError("locked")] * 5)

    with pytest.raises(PermissionError):
        save_json(path, {"first_name": "John"})

    assert len(calls) == 5
    assert waits == [0.05, 0.1, 0.2, 0.4]
    assert list(tmp_path.iterdir()) == [path]
    assert read_json(path) == {"first_name": "Jane"}


def test_does_not_retry_other_disk_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profile.json"
    waits, calls = _fail_replace(monkeypatch, [OSError(errno.ENOSPC, "No space left on device")])

    with pytest.raises(OSError, match="space"):
        save_json(path, {"first_name": "John"})

    assert len(calls) == 1
    assert waits == []
    assert list(tmp_path.iterdir()) == []


def test_every_save_writes_through_its_own_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two tabs saving the same file at once must not share a temp file."""
    path = tmp_path / "profile.json"
    names: list[str] = []
    real_replace = os.replace

    def spy(src: Path, dst: Path) -> None:
        names.append(Path(src).name)
        real_replace(src, dst)

    monkeypatch.setattr(repo, "os", SimpleNamespace(replace=spy))

    save_json(path, {"n": 1})
    save_json(path, {"n": 2})

    assert len(names) == 2
    assert names[0] != names[1]
    assert list(tmp_path.iterdir()) == [path]

"""What the app writes is readable only by the account that runs it.

The profile, the CVs, the previews and the sessions Reflex saves to disk are personal
data. With the usual umask they came out readable by every other account on the computer.
"""

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from cv_generator.app import private_files
from cv_generator.app.config import DATA_DIR, OUTPUT_DIR
from cv_generator.app.private_files import keep_app_files_private, keep_private

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Windows keeps the user's folders private with ACLs")


@pytest.fixture(autouse=True)
def usual_umask() -> Iterator[None]:
    """The umask is the whole process's: each test starts from the usual one and leaves it."""
    previous = os.umask(0o022)
    yield
    os.umask(previous)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_closes_the_folders_that_already_hold_personal_data(tmp_path: Path) -> None:
    """Another account cannot go into a closed folder, whatever the mode of the files inside."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "profile.json").write_text("{}", encoding="utf-8")
    assert _mode(data) == 0o755

    keep_private([data, tmp_path / "not-created-yet"])

    assert _mode(data) == 0o700
    assert not (tmp_path / "not-created-yet").exists()


def test_what_is_written_afterwards_is_the_owner_s_alone(tmp_path: Path) -> None:
    keep_private([])

    (tmp_path / "cv.pdf").write_bytes(b"%PDF")
    (tmp_path / "output").mkdir()

    assert _mode(tmp_path / "cv.pdf") == 0o600
    assert _mode(tmp_path / "output") == 0o700


def test_covers_every_folder_with_personal_data(upload_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[Path] = []
    monkeypatch.setattr(private_files, "keep_private", closed.extend)

    keep_app_files_private()

    assert closed == [DATA_DIR, OUTPUT_DIR, upload_dir, Path(".states")]


def test_the_backend_keeps_them_private_from_the_start() -> None:
    """A lifespan task, not an import: the tests import the app and would close the real folders."""
    from cv_generator.app.app import app

    assert keep_app_files_private in app._lifespan_tasks  # noqa: SLF001

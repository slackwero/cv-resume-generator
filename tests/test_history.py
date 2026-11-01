"""The history index: what is listed, what is hidden and what is never lost.

Archiving is the only operation that takes a CV out of view. It deletes nothing, because
the history is only useful if what you sent is still there and can be produced again.
"""

from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.storage.history import (
    HistoryEntry,
    archive_cv,
    load_history,
    note_archive_reason,
    rename_entry,
    save_history,
)
from cv_generator.storage.repo import save_json


def _entry(cv_id: str, name: str) -> HistoryEntry:
    return HistoryEntry(
        cv_id=cv_id,
        cv_name=name,
        target_role="DevSecOps Engineer",
        language="es",
        template="modern",
        created=datetime(2026, 8, 28, 10, 0, 0),  # noqa: DTZ001
        pdf_file=f"/output/{cv_id}.pdf",
    )


def test_a_new_entry_is_not_archived(tmp_path: Path) -> None:
    save_history(tmp_path, [_entry("cv-1", "Northwind")])

    assert load_history(tmp_path)[0].archived is False


def test_archive_marks_only_the_requested_cv(tmp_path: Path) -> None:
    save_history(tmp_path, [_entry("cv-1", "Northwind"), _entry("cv-2", "Contoso")])

    archive_cv(tmp_path, "cv-1", archived=True)

    by_id = {entry.cv_id: entry.archived for entry in load_history(tmp_path)}
    assert by_id == {"cv-1": True, "cv-2": False}


def test_archive_does_not_delete_the_entry(tmp_path: Path) -> None:
    """The regression that matters: archiving has to hide, never lose."""
    save_history(tmp_path, [_entry("cv-1", "Northwind")])

    archive_cv(tmp_path, "cv-1", archived=True)

    entries = load_history(tmp_path)
    assert len(entries) == 1
    assert entries[0].pdf_file == "/output/cv-1.pdf"


def test_unarchiving_returns_the_cv_to_the_list(tmp_path: Path) -> None:
    save_history(tmp_path, [_entry("cv-1", "Northwind")])
    archive_cv(tmp_path, "cv-1", archived=True)

    archive_cv(tmp_path, "cv-1", archived=False)

    assert load_history(tmp_path)[0].archived is False


def test_archiving_a_missing_cv_fails_instead_of_doing_nothing(tmp_path: Path) -> None:
    """Failing silently would leave the interface believing it archived something."""
    save_history(tmp_path, [_entry("cv-1", "Northwind")])

    with pytest.raises(KeyError):
        archive_cv(tmp_path, "cv-ghost", archived=True)


def test_renaming_changes_only_the_name_of_that_cv(tmp_path: Path) -> None:
    """What you decided after generating stays: an archived CV keeps its date and reason."""
    save_history(tmp_path, [_entry("cv-1", "Northwind"), _entry("cv-2", "Contoso")])
    archive_cv(tmp_path, "cv-1", archived=True)
    note_archive_reason(tmp_path, "cv-1", "The posting closed")
    before = load_history(tmp_path)

    rename_entry(tmp_path, "cv-1", "Northwind, platform team")

    by_id = {entry.cv_id: entry for entry in load_history(tmp_path)}
    assert by_id["cv-1"].cv_name == "Northwind, platform team"
    assert by_id["cv-2"].cv_name == "Contoso"
    renamed = by_id["cv-1"].model_dump(exclude={"cv_name"})
    assert renamed == next(e for e in before if e.cv_id == "cv-1").model_dump(exclude={"cv_name"})


def test_renaming_a_missing_cv_fails_instead_of_doing_nothing(tmp_path: Path) -> None:
    save_history(tmp_path, [_entry("cv-1", "Northwind")])

    with pytest.raises(KeyError):
        rename_entry(tmp_path, "cv-ghost", "Contoso")


def test_an_index_written_before_the_field_is_still_valid(tmp_path: Path) -> None:
    """`archived` came after the initial design; indexes already written do not carry it."""
    save_json(
        tmp_path / "history.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "cv_id": "cv-old",
                    "cv_name": "Northwind",
                    "target_role": "DevSecOps Engineer",
                    "language": "es",
                    "template": "modern",
                    "created": "2026-03-01T10:00:00",
                    "pdf_file": "/output/cv-old.pdf",
                }
            ],
        },
    )

    entries = load_history(tmp_path)

    assert len(entries) == 1
    assert entries[0].archived is False
    assert entries[0].has_posting is False

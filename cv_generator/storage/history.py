"""Index of the generated CV history.

The index exists so the home page does not have to open one file per CV at startup.
Almost all its columns are a cache: they come from the snapshot in data/cvs/, which
is the source of truth for WHAT you sent, and can be recomputed from it.

Almost all, not all. What you decide after generating —archiving a CV, when, and
why— is in no snapshot and cannot be recomputed from anywhere. That is the limit of
"it is a cache" and the reason for `USER_SET_FIELDS`: rebuilding combines one with
the other instead of redoing everything.
"""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from cv_generator.models.cv import GeneratedCV
from cv_generator.storage.repo import read_json, save_json

HISTORY_FILE = "history.json"
CVS_SUBDIR = "cvs"

# What the user decides AFTER generating, and that no snapshot knows.
#
# It is the distinction that matters when rebuilding: `has_posting` is derived again
# from the snapshot without trouble, but if you archived a CV on Tuesday and wrote why,
# that is nowhere else. A rebuild that does not bring it over from the previous index
# is not recomputing it: it is deleting it.
USER_SET_FIELDS = frozenset({"archived", "archived_at", "archive_reason"})

# Index fields that do not come from the GeneratedCV: `has_posting` is derived from the
# snapshot and the user sets the rest.
#
# This set is what `from_cv` subtracts to know what to inherit from the snapshot, so
# every field that lives ONLY in the index has to be here. If one is forgotten, the
# generated CV does not bring it, the rebuild cannot fill it, and the data disappears
# without anyone noticing.
INDEX_ONLY_FIELDS = frozenset({"has_posting"}) | USER_SET_FIELDS


class HistoryEntry(BaseModel):
    """The row the home page shows for each generated CV."""

    cv_id: str
    cv_name: str
    target_role: str
    language: str
    template: str
    created: datetime
    pdf_file: str

    # Derived from the snapshot. It lives in the index so the home page can tell whether a
    # CV had a posting without opening one file per row, which is exactly what the index avoids.
    # The default keeps indexes written before this field valid; `rebuild_history`
    # fills them in.
    has_posting: bool = False

    # Archiving hides the row from the default view; it deletes nothing. A history that is
    # only useful if what you sent is still there cannot offer a delete button, but
    # immutable does not mean everything has to stay in view forever either.
    archived: bool = False

    # When and why you took it off the list.
    #
    # The date is recorded automatically on archive: it costs nothing, and six months later
    # it is the difference between "this is archived" and "I archived this the day they
    # told me no". The reason is optional and written afterwards, on the row itself: asking
    # for it up front would put ceremony on a reversible action, which is exactly the
    # opposite of what this product does.
    #
    # Both have defaults, like `has_posting`, so indexes written before these fields stay
    # valid.
    archived_at: datetime | None = None
    archive_reason: str = ""

    @classmethod
    def from_cv(cls, cv: GeneratedCV) -> "HistoryEntry":
        inherited = set(cls.model_fields) - INDEX_ONLY_FIELDS
        return cls(**cv.model_dump(include=inherited), has_posting=cv.posting is not None)


def _index_path(data_dir: Path) -> Path:
    return data_dir / HISTORY_FILE


def cvs_dir(data_dir: Path) -> Path:
    return data_dir / CVS_SUBDIR


def _sort(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    """The newest CV first, which is how a history reads."""
    return sorted(entries, key=lambda entry: entry.created, reverse=True)


def load_history(data_dir: Path) -> list[HistoryEntry]:
    """Reads the index. Returns an empty list if no CV has been generated yet."""
    path = _index_path(data_dir)
    if not path.is_file():
        return []

    data = read_json(path)
    return _sort([HistoryEntry.model_validate(item) for item in data.get("entries", [])])


def save_history(data_dir: Path, entries: list[HistoryEntry]) -> None:
    """Rewrites the whole index."""
    data_dir.mkdir(parents=True, exist_ok=True)
    save_json(
        _index_path(data_dir),
        {
            "schema_version": 1,
            "entries": [entry.model_dump(mode="json") for entry in _sort(entries)],
        },
    )


def register_cv(data_dir: Path, cv: GeneratedCV) -> None:
    """Adds a freshly generated CV to the index."""
    entries = [e for e in load_history(data_dir) if e.cv_id != cv.cv_id]
    save_history(data_dir, [*entries, HistoryEntry.from_cv(cv)])


def archive_cv(data_dir: Path, cv_id: str, *, archived: bool) -> list[HistoryEntry]:
    """Hides a CV from the history view, or brings it back.

    It does not touch the snapshot or the PDF: it only marks the row. What you sent is
    still there and can be produced again, which is the only thing the history promises.

    Archiving stamps the date; restoring clears date and reason, because they belong to
    one specific archiving and not to the CV. If you archive it again, it is a new one.

    Raises:
        KeyError: if there is no CV with that id.
    """
    entries = load_history(data_dir)
    if not any(entry.cv_id == cv_id for entry in entries):
        raise KeyError(f"there is no CV with id {cv_id!r}")

    change = (
        {"archived": True, "archived_at": datetime.now(UTC).replace(tzinfo=None)}
        if archived
        else {"archived": False, "archived_at": None, "archive_reason": ""}
    )
    updated_entries = [entry.model_copy(update=change) if entry.cv_id == cv_id else entry for entry in entries]
    save_history(data_dir, updated_entries)
    return updated_entries


def note_archive_reason(data_dir: Path, cv_id: str, reason: str) -> list[HistoryEntry]:
    """Writes (or clears) the reason a CV was archived.

    It is noted afterwards, on the row that is already archived, not in a dialog up
    front: archiving is reversible and does not deserve ceremony, but six months later
    the reason is the only thing that explains why that CV is not on the list.

    Raises:
        KeyError: if there is no CV with that id.
    """
    entries = load_history(data_dir)
    if not any(entry.cv_id == cv_id for entry in entries):
        raise KeyError(f"there is no CV with id {cv_id!r}")

    updated_entries = [
        entry.model_copy(update={"archive_reason": reason.strip()}) if entry.cv_id == cv_id else entry
        for entry in entries
    ]
    save_history(data_dir, updated_entries)
    return updated_entries


def rebuild_history(data_dir: Path) -> list[HistoryEntry]:
    """Rebuilds the index from the snapshots, in case it was lost or fell out of date.

    The snapshots are the source of truth for WHAT you sent, but they know nothing about
    what you decided later. That is why this is not a plain rebuild: what comes out of
    the snapshot is combined with what the user set in the previous index
    (`USER_SET_FIELDS`), which cannot be recomputed from anywhere.

    It used not to combine them, and rebuilding put every archived CV back on the list,
    with its date and reason erased. The index is a cache, but not all of its columns
    are.

    A CV whose snapshot is gone disappears from the index: that part is a cache, and the
    function exists precisely so the index tells the truth again.
    """
    directory = cvs_dir(data_dir)
    snapshots = sorted(directory.glob("*.json")) if directory.is_dir() else []

    kept = {entry.cv_id: entry.model_dump(include=set(USER_SET_FIELDS)) for entry in load_history(data_dir)}

    entries = []
    for path in snapshots:
        entry = HistoryEntry.from_cv(GeneratedCV.model_validate(read_json(path)))
        previous_one = kept.get(entry.cv_id)
        entries.append(entry.model_copy(update=previous_one) if previous_one else entry)

    save_history(data_dir, entries)
    return _sort(entries)

"""Access to the master profile and to the status of the last sync.

It isolates the interface from the details of where and how the files are stored.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from cv_generator.models.profile import MasterProfile
from cv_generator.storage.repo import read_json, save_json

PROFILE_FILE = "profile.json"
SYNC_FILE = "sync_state.json"

# Placeholder for the required fields the importer cannot fill: LinkedIn does not
# provide the phone. The profile is created anyway and the app asks you to complete it,
# instead of blocking the first sync over a piece of data the source never brings.
PENDING_FIELD = "PENDING"

# The five fields the CV cannot print empty.
REQUIRED_PERSONAL_FIELDS = ("first_name", "last_name", "profession", "phone", "email")


class SyncStatus(BaseModel):
    """What was imported last time and from where. It feeds the home page notice."""

    source: str
    timestamp: datetime
    ok: bool = True
    detected_language: str = "en"
    imported_items: dict[str, int] = Field(default_factory=dict)


def backup_profile(data_dir: Path, moment: datetime) -> Path | None:
    """Copies the current profile before overwriting it.

    Accepting a conflict replaces a text the user rewrote by hand, and that is the only
    irreversible operation the product performs on the source of truth. The copy is
    what lets it say "you can go back" instead of "this cannot be undone".

    Returns None if there was no profile to back up yet.
    """
    origin = data_dir / PROFILE_FILE
    if not origin.is_file():
        return None

    target = data_dir / f"profile.{moment:%Y%m%d-%H%M%S}.json"
    target.write_bytes(origin.read_bytes())
    return target


def available_backups(data_dir: Path) -> list[Path]:
    """Profile backups, newest first."""
    return sorted(data_dir.glob("profile.*.json"), reverse=True)


def restore_backup(data_dir: Path, name: str) -> MasterProfile:
    """Puts the profile back the way it was before a sync.

    The name is compared against the backups that actually exist instead of building a
    path with it: it comes from the interface state and must not be able to point to
    any file outside the data directory.

    Raises:
        FileNotFoundError: if that backup does not exist.
    """
    candidates = {path.name: path for path in available_backups(data_dir)}
    origin = candidates.get(name)
    if origin is None:
        raise FileNotFoundError(f"the backup {name!r} does not exist")

    profile = MasterProfile.model_validate(read_json(origin))
    save_profile(data_dir, profile)
    return profile


def pending_fields(profile: MasterProfile) -> list[str]:
    """Required fields that still hold the placeholder and must be completed by hand."""
    return [field for field in REQUIRED_PERSONAL_FIELDS if getattr(profile.personal, field, "") == PENDING_FIELD]


def load_profile(data_dir: Path) -> MasterProfile | None:
    """Returns the master profile, or None if none was created yet."""
    path = data_dir / PROFILE_FILE
    return MasterProfile.model_validate(read_json(path)) if path.is_file() else None


def save_profile(data_dir: Path, profile: MasterProfile) -> None:
    """Persists the master profile."""
    data_dir.mkdir(parents=True, exist_ok=True)
    save_json(data_dir / PROFILE_FILE, profile.model_dump(mode="json"))


def load_sync_status(data_dir: Path) -> SyncStatus | None:
    """Returns the last sync, or None if it never synced."""
    path = data_dir / SYNC_FILE
    return SyncStatus.model_validate(read_json(path)) if path.is_file() else None


def save_sync_status(data_dir: Path, status: SyncStatus) -> None:
    """Records the result of a sync."""
    data_dir.mkdir(parents=True, exist_ok=True)
    save_json(data_dir / SYNC_FILE, status.model_dump(mode="json"))

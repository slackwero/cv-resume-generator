"""Access to the master profile and to the status of the last sync.

It isolates the interface from the details of where and how the files are stored.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from cv_generator.models.profile import FIRST_PROFESSION_ID, MasterProfile, PersonalInfo, Profession
from cv_generator.services.placeholders import PENDING_FIELD  # noqa: F401  (re-exported: callers import it from here)
from cv_generator.services.translations import text_key
from cv_generator.storage.repo import read_json, save_json

PROFILE_FILE = "profile.json"
SYNC_FILE = "sync_state.json"

# Where a profile from before the list (schema 2) kept the Spanish of its single headline.
# Only the upgrade reads it, so it stays here after the translations stopped using it.
LEGACY_PROFESSION_KEY = "personal.profession"

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

    profile = _upgraded(data_dir, MasterProfile.model_validate(read_json(origin)))
    save_profile(data_dir, profile)
    return profile


def pending_fields(profile: MasterProfile) -> list[str]:
    """Required fields that still hold the placeholder and must be completed by hand."""
    return [field for field in REQUIRED_PERSONAL_FIELDS if getattr(profile.personal, field, "") == PENDING_FIELD]


def _upgraded(data_dir: Path, profile: MasterProfile) -> MasterProfile:
    """The profile as schema 3, in memory; the file is only rewritten by a save."""
    if profile.source_language is None:
        # LinkedIn fed the profile in the language of the last sync; never synced means
        # the profile was typed in by hand, in English.
        status = load_sync_status(data_dir)
        profile.source_language = status.detected_language if status else "en"
    if not profile.professions:
        profile.professions = [Profession(id=FIRST_PROFESSION_ID, text=profile.personal.profession)]
        # The Spanish of the old single headline now belongs to the first entry, intact.
        for entries in profile.translations.values():
            moved = entries.pop(LEGACY_PROFESSION_KEY, None)
            if moved is not None:
                entries[text_key(FIRST_PROFESSION_ID, "text")] = moved
    profile.schema_version = 3
    return profile


def load_profile(data_dir: Path) -> MasterProfile | None:
    """Returns the master profile, or None if none was created yet.

    A profile saved before the bilingual content comes back upgraded in memory: the file
    is only rewritten by the next save.
    """
    path = data_dir / PROFILE_FILE
    if not path.is_file():
        return None

    return _upgraded(data_dir, MasterProfile.model_validate(read_json(path)))


def save_profile(data_dir: Path, profile: MasterProfile) -> None:
    """Persists the master profile.

    The first save over a profile from before schema 3 keeps a copy of it: the upgrade
    adds fields an older version of the app would drop.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / PROFILE_FILE
    # Read the file, not the profile: the profile was already upgraded in memory.
    if path.is_file() and read_json(path).get("schema_version", 1) < 3:
        backup_profile(data_dir, datetime.now())
    save_json(path, profile.model_copy(update={"schema_version": 3}).model_dump(mode="json"))


def with_personal(profile: MasterProfile, personal: PersonalInfo) -> MasterProfile:
    """Returns the profile with these contact details and everything else as it was.

    The photo is kept from the given profile: it saves on its own, and the contact form
    does not carry it. The given profile is not modified.
    """
    result = profile.model_copy(deep=True)
    result.personal = personal.model_copy(update={"photo": profile.personal.photo})
    return result


def load_sync_status(data_dir: Path) -> SyncStatus | None:
    """Returns the last sync, or None if it never synced."""
    path = data_dir / SYNC_FILE
    return SyncStatus.model_validate(read_json(path)) if path.is_file() else None


def save_sync_status(data_dir: Path, status: SyncStatus) -> None:
    """Records the result of a sync."""
    data_dir.mkdir(parents=True, exist_ok=True)
    save_json(data_dir / SYNC_FILE, status.model_dump(mode="json"))

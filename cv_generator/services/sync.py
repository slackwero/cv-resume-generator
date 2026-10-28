"""Orchestration of a LinkedIn sync.

A sync is never applied on its own: it is first analyzed and changes are proposed,
and only what the user accepts is written.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from cv_generator.importers.base import PartialPersonalInfo, ProfileDraft
from cv_generator.importers.linkedin_pdf import import_from_pdf
from cv_generator.importers.linkedin_zip import import_from_zip
from cv_generator.importers.merge import Change, ChangeKind, apply_changes, compute_diff
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services.profile import (
    PENDING_FIELD,
    SyncStatus,
    backup_profile,
    save_profile,
    save_sync_status,
)

# What is new and what changed on LinkedIn are proposed already checked. A conflict is
# not: accepting it means discarding a text the user rewrote by hand, and that decision
# has to be theirs and explicit.
PRESELECTED_KINDS = (ChangeKind.NEW, ChangeKind.MODIFIED)


class ApplyResult(BaseModel):
    """The resulting profile and where the copy of the previous one went."""

    profile: MasterProfile
    backup: Path | None = None


class AnalysisResult(BaseModel):
    """What a sync proposes, before touching anything."""

    changes: list[Change] = Field(default_factory=list)
    detected_language: str = "en"
    source: str = "linkedin_pdf"

    # The contact details travel with the analysis because they are the only thing needed
    # to create the profile when none exists yet.
    personal: PartialPersonalInfo = Field(default_factory=PartialPersonalInfo)


# Each export format has its importer; all of them produce a ProfileDraft.
IMPORTERS: dict[str, tuple[str, Callable[[Path], ProfileDraft]]] = {
    ".pdf": ("linkedin_pdf", import_from_pdf),
    ".zip": ("linkedin_zip", import_from_zip),
}


def _compare(draft: ProfileDraft, profile: MasterProfile, source: str) -> AnalysisResult:
    return AnalysisResult(
        changes=compute_diff(profile, draft),
        detected_language=draft.detected_language,
        source=source,
        personal=draft.personal,
    )


def empty_profile() -> MasterProfile:
    """A profile with no data, only to compare against.

    `compute_diff` never reads `personal`, so a profile built without validation is
    enough for the diff. It is never saved: writing to disk is the job of
    `create_initial_profile`, which does produce a valid model.
    """
    return MasterProfile.model_construct(personal=None)


def create_initial_profile(personal: PartialPersonalInfo) -> MasterProfile:
    """Builds the master profile from the imported contact details.

    What the importer did not bring is marked as pending instead of empty: the model
    requires the five fields, and a visible placeholder the app asks you to fix is
    better than preventing the first sync.
    """
    return MasterProfile(
        personal=PersonalInfo(
            first_name=personal.first_name or PENDING_FIELD,
            last_name=personal.last_name or PENDING_FIELD,
            profession=personal.profession or PENDING_FIELD,
            phone=personal.phone or PENDING_FIELD,
            email=personal.email or PENDING_FIELD,
            website=personal.website,
            country=personal.country,
        )
    )


def analyze_pdf(path: Path, profile: MasterProfile) -> AnalysisResult:
    """Reads the LinkedIn profile PDF and compares it with the master profile."""
    return _compare(import_from_pdf(path), profile, "linkedin_pdf")


def analyze_zip(path: Path, profile: MasterProfile) -> AnalysisResult:
    """Reads the LinkedIn ZIP export and compares it with the master profile."""
    return _compare(import_from_zip(path), profile, "linkedin_zip")


def analyze_file(path: Path, profile: MasterProfile) -> AnalysisResult:
    """Picks the importer by the file extension.

    Raises:
        ValueError: if the file is neither a profile PDF nor a ZIP export.
    """
    chosen = IMPORTERS.get(path.suffix.lower())
    if chosen is None:
        supported = ", ".join(sorted(IMPORTERS))
        raise ValueError(f"unsupported format: {path.suffix!r}. Accepted: {supported}")

    source, importer = chosen
    return _compare(importer(path), profile, source)


def preselection(changes: list[Change]) -> set[str]:
    """Keys of the changes that are proposed checked from the start."""
    return {change.key for change in changes if change.kind in PRESELECTED_KINDS}


def summary_by_kind(changes: list[Change]) -> dict[ChangeKind, int]:
    """Counts the changes of each kind, for the screen header."""
    tally = dict.fromkeys(ChangeKind, 0)
    for change in changes:
        tally[change.kind] += 1
    return tally


def _inventory(profile: MasterProfile) -> dict[str, int]:
    return {
        "experiences": len(profile.experiences),
        "achievements": sum(len(experience.achievements) for experience in profile.experiences),
        "skills": len(profile.skills),
        "languages": len(profile.languages),
        "education": len(profile.education),
        "courses": len(profile.courses),
        "profile_texts": len(profile.profile_texts),
    }


def apply_sync(
    *,
    profile: MasterProfile,
    changes: list[Change],
    accepted_items: set[str],
    data_dir: Path,
    source: str,
    detected_language: str,
    moment: datetime | None = None,
) -> ApplyResult:
    """Applies the accepted changes, saves the profile and records the sync.

    The given profile is not modified: a new one is returned, and that is the one
    written to disk. The previous one is backed up before being overwritten.
    """
    result = apply_changes(profile, changes, accepted_items)
    when = moment or datetime.now()  # noqa: DTZ005

    backup = backup_profile(data_dir, when)
    save_profile(data_dir, result)
    save_sync_status(
        data_dir,
        SyncStatus(
            source=source,
            timestamp=when,
            ok=True,
            detected_language=detected_language,
            imported_items=_inventory(result),
        ),
    )
    return ApplyResult(profile=result, backup=backup)

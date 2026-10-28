"""State of the LinkedIn sync screen."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.importers.base import PartialPersonalInfo
from cv_generator.importers.merge import Change, ChangeKind
from cv_generator.models.profile import MasterProfile
from cv_generator.services.profile import load_profile, restore_backup
from cv_generator.services.sync import (
    IMPORTERS,
    analyze_file,
    apply_sync,
    create_initial_profile,
    empty_profile,
    preselection,
    summary_by_kind,
)
from cv_generator.text import plural

UPLOAD_ID = "export_linkedin"


# The file is always saved with this base name: the one the browser sends is user data
# and must not be used to build a path. The extension decides which importer is used,
# so it is taken from the list of supported formats and never from the received name.
SAFE_FILENAME = "export_linkedin"

PHASE_CHOOSE = "choose"
PHASE_REVIEW = "review"
PHASE_APPLIED = "applied"

KIND_LABELS = {
    ChangeKind.NEW: "New",
    ChangeKind.MODIFIED: "Changed on LinkedIn",
    ChangeKind.CONFLICT: "Conflict",
    ChangeKind.UNCHANGED: "Unchanged",
}

SECTION_LABELS = {
    "profile_texts": "Profile text",
    "experiences": "Experience",
    "achievements": "Achievement",
    "skills": "Skill",
    "languages": "Language",
    "education": "Education",
    "courses": "Course",
}

# Conflicts first: they are the only ones that require a decision from the user.
REVIEW_ORDER = [ChangeKind.CONFLICT, ChangeKind.MODIFIED, ChangeKind.NEW]

# Heading of each review block. Without them, conflicts and new items share one flat
# scroll, told apart only by a badge on each row.
GROUP_TITLES = {
    ChangeKind.CONFLICT: "Conflicts",
    ChangeKind.MODIFIED: "Changes on LinkedIn",
    ChangeKind.NEW: "New on LinkedIn",
}

GROUP_HINTS = {
    ChangeKind.CONFLICT: "You rewrote these texts and they also changed on LinkedIn. Accepting replaces yours.",
    ChangeKind.MODIFIED: "They changed on LinkedIn and you had not touched them.",
    ChangeKind.NEW: "They are not in your profile yet.",
}


class SyncState(rx.State):
    """Drives the analyze -> review -> apply cycle."""

    _profile: MasterProfile | None = None
    _changes: list[Change] = []
    _imported_personal: PartialPersonalInfo = PartialPersonalInfo()

    phase: str = PHASE_CHOOSE
    # `error_message` is what failed; `notice` is context that is not a failure. Sharing a
    # single variable forced the notices to be painted with the red error callout.
    error_message: str = ""
    notice: str = ""
    analyzing: bool = False
    applying: bool = False
    is_first_profile: bool = False
    detected_language: str = ""
    source: str = "linkedin_pdf"

    visible_changes: list[dict[str, str]] = []
    # The same list with a heading before each block. Reflex cannot filter inside a
    # foreach, so the groups and their rows travel flattened.
    change_rows: list[dict[str, str]] = []
    accepted_items: dict[str, bool] = {}

    new_count: int = 0
    modified_count: int = 0
    conflict_count: int = 0
    unchanged_count: int = 0

    result_summary: str = ""
    backup_path: str = ""
    undoing: bool = False
    undone: bool = False

    @rx.event
    def start(self) -> None:
        """Leaves the screen ready for a new sync."""
        self.phase = PHASE_CHOOSE
        self.error_message = ""
        self.notice = ""
        self.result_summary = ""
        self.visible_changes = []
        self.change_rows = []
        self.accepted_items = {}
        self.backup_path = ""
        self.undone = False
        self._changes = []

        self._profile = load_profile(DATA_DIR)
        self.is_first_profile = self._profile is None
        if self.is_first_profile:
            self.notice = (
                "There is no profile yet. This first sync will create it with "
                "whatever the file brings, and afterwards you can complete what is missing."
            )

    @rx.event
    async def process_file(self, files: list[rx.UploadFile]) -> AsyncGenerator[None, None]:
        """Saves the uploaded export and works out what would change in the profile.

        Parsing a whole LinkedIn ZIP takes seconds. The `yield` sends the loading state
        before starting and the work runs in a thread, so the screen does not go silent
        in the meantime.
        """
        if self.analyzing:
            return

        if not files:
            self.error_message = "No file was received. Drag the ZIP or the PDF onto the box and try again."
            return

        extension = Path(files[0].name or "").suffix.lower()
        if extension not in IMPORTERS:
            supported = ", ".join(sorted(IMPORTERS))
            kind = extension or "of a type I do not recognize"
            self.error_message = f"That file is {kind}. Accepted: {supported}"
            return

        self.analyzing = True
        self.error_message = ""
        yield

        try:
            content = await files[0].read()
        except OSError as error:
            self.error_message = f"The uploaded file could not be read: {error}"
            self.analyzing = False
            return

        target = rx.get_upload_dir() / f"{SAFE_FILENAME}{extension}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

        await self._analyze(target)
        self.analyzing = False

    async def _analyze(self, path: Path) -> None:
        # Without a profile it is compared against an empty one: everything imported comes out
        # as NEW and preselected, which is exactly what is needed the first time.
        profile = self._profile or empty_profile()

        try:
            result = await asyncio.to_thread(analyze_file, path, profile)
        except (ValueError, OSError, KeyError) as error:
            hint_text = (
                "Check that it is the ZIP you downloaded from LinkedIn, not unzipped."
                if path.suffix.lower() == ".zip"
                else "Check that it is the PDF LinkedIn generates with More > Save to PDF."
            )
            self.error_message = f"The LinkedIn export could not be read: {error}. {hint_text}"
            return

        self._changes = result.changes
        self._imported_personal = result.personal
        self.detected_language = result.detected_language
        self.source = result.source

        tally = summary_by_kind(result.changes)
        self.new_count = tally[ChangeKind.NEW]
        self.modified_count = tally[ChangeKind.MODIFIED]
        self.conflict_count = tally[ChangeKind.CONFLICT]
        self.unchanged_count = tally[ChangeKind.UNCHANGED]

        marked_items = preselection(result.changes)
        actionable = [c for c in result.changes if c.kind is not ChangeKind.UNCHANGED]
        actionable.sort(key=lambda c: REVIEW_ORDER.index(c.kind))

        self.accepted_items = {change.key: change.key in marked_items for change in actionable}
        self.visible_changes = [
            {
                "key": change.key,
                "kind": str(change.kind),
                "kind_label": KIND_LABELS[change.kind],
                "section": SECTION_LABELS.get(change.section, change.section),
                "current_text": change.current_text or "",
                "incoming_text": change.incoming_text or change.label,
            }
            for change in actionable
        ]
        self.change_rows = self._group(actionable)

        self.phase = PHASE_REVIEW
        self.error_message = ""

    def _group(self, actionable: list[Change]) -> list[dict[str, str]]:
        """Inserts a heading before the first change of each kind."""
        rows: list[dict[str, str]] = []
        seen: set[ChangeKind] = set()
        tally = summary_by_kind(actionable)

        for change in actionable:
            if change.kind not in seen:
                seen.add(change.kind)
                rows.append(
                    {
                        "row": "group",
                        "key": f"group:{change.kind}",
                        "kind": str(change.kind),
                        "title": GROUP_TITLES[change.kind],
                        "tally": str(tally[change.kind]),
                        "hint": GROUP_HINTS[change.kind],
                    }
                )
            rows.append(
                {
                    "row": "change",
                    "key": change.key,
                    "kind": str(change.kind),
                    "kind_label": KIND_LABELS[change.kind],
                    "section": SECTION_LABELS.get(change.section, change.section),
                    "current_text": change.current_text or "",
                    "incoming_text": change.incoming_text or change.label,
                }
            )
        return rows

    @rx.var
    def nothing_to_do(self) -> bool:
        return len(self.visible_changes) == 0

    @rx.var
    def accepted_total(self) -> int:
        return sum(1 for accepted in self.accepted_items.values() if accepted)

    @rx.var
    def accepted_conflicts(self) -> list[str]:
        """Your own texts that would be lost if it were applied right now."""
        return [
            change["current_text"]
            for change in self.visible_changes
            if change["kind"] == str(ChangeKind.CONFLICT) and self.accepted_items.get(change["key"], False)
        ]

    @rx.var
    def accepted_conflicts_total(self) -> int:
        return len(self.accepted_conflicts)

    @rx.var
    def has_accepted_conflicts(self) -> bool:
        return len(self.accepted_conflicts) > 0

    @rx.event
    def toggle(self, key: str, value: bool) -> None:
        self.accepted_items[key] = value

    @rx.event
    def mark_all(self) -> None:
        self.accepted_items = dict.fromkeys(self.accepted_items, True)

    @rx.event
    def unmark_all(self) -> None:
        self.accepted_items = dict.fromkeys(self.accepted_items, False)

    @rx.event
    def restore_suggestion(self) -> None:
        """Goes back to the original proposal: the safe ones checked, the conflicts not."""
        marked_items = preselection(self._changes)
        self.accepted_items = {key: key in marked_items for key in self.accepted_items}

    @rx.event
    async def apply(self) -> AsyncGenerator[None, None]:
        """Writes only the accepted changes to the profile.

        If there was no profile yet, this is when it is created: with the contact details
        the importer brought and a placeholder in the required fields that did not come.
        """
        if self.applying:
            return

        self.applying = True
        self.error_message = ""
        yield

        base = self._profile or create_initial_profile(self._imported_personal)
        accepted_items = {key for key, value in self.accepted_items.items() if value}
        try:
            result = await asyncio.to_thread(
                apply_sync,
                profile=base,
                changes=self._changes,
                accepted_items=accepted_items,
                data_dir=DATA_DIR,
                source=self.source,
                detected_language=self.detected_language,
            )
        except (OSError, ValueError) as error:
            self.error_message = f"The sync could not be applied and your profile was left intact: {error}"
            self.applying = False
            return

        profile = result.profile
        achievements = sum(len(experience.achievements) for experience in profile.experiences)
        changes = plural(len(accepted_items), "change", "changes")
        experiences = plural(len(profile.experiences), "experience", "experiences")
        self.result_summary = (
            f"Applied {changes}. Your profile now has "
            f"{experiences} and {plural(achievements, 'achievement', 'achievements')}."
        )
        self.backup_path = result.backup.name if result.backup else ""
        self.phase = PHASE_APPLIED
        self.error_message = ""
        self.applying = False

    @rx.event
    async def undo(self) -> AsyncGenerator[None, None]:
        """Puts the profile back to the backup saved before applying.

        Without this, the conflict dialog's "in case you want to go back" was decorative:
        the copy was written to disk and no screen read it.
        """
        if self.undoing or not self.backup_path:
            return

        self.undoing = True
        self.error_message = ""
        yield

        try:
            profile = await asyncio.to_thread(restore_backup, DATA_DIR, self.backup_path)
        except (FileNotFoundError, ValueError, OSError) as error:
            self.error_message = f"The backup could not be restored: {error}"
            self.undoing = False
            return

        self._profile = profile
        achievements = sum(len(experience.achievements) for experience in profile.experiences)
        self.result_summary = (
            "The sync was undone. Your profile is back to "
            f"{plural(len(profile.experiences), 'experience', 'experiences')} and "
            f"{plural(achievements, 'achievement', 'achievements')}."
        )
        self.undone = True
        self.undoing = False

    @rx.event
    def back_to_home(self) -> rx.event.EventSpec:
        return rx.redirect("/")

    @rx.event
    def go_to_profile(self) -> rx.event.EventSpec:
        return rx.redirect("/profile")

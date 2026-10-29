"""State of the Work experience subsection of My profile.

The owner edits, duplicates, adds, removes and reorders the achievements of each job.
The jobs themselves (role, company, dates) come from LinkedIn and are read-only here.
Every operation saves right away, like the skills.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.models.profile import MasterProfile
from cv_generator.services import achievements as achievement_operations
from cv_generator.services.achievements import origin_of
from cv_generator.services.profile import load_profile, save_profile

# Every row carries every key: `rx.foreach` walks a single dict type and does not like
# some rows carrying keys others do not.
ROW_KEYS = (
    "row",
    "key",
    "experience_id",
    "achievement_id",
    "role",
    "company",
    "dates",
    "count",
    "text",
    "origin",
    "linkedin_text",
    "first",
    "last",
)


def _row(**values: str) -> dict[str, str]:
    return {**dict.fromkeys(ROW_KEYS, ""), **values}


def _count(total: int) -> str:
    if total == 0:
        return "No achievements"
    if total == 1:
        return "1 achievement"
    return f"{total} achievements"


def achievement_rows(profile: MasterProfile) -> list[dict[str, str]]:
    """Each job, its achievements and its add row, flattened in profile order.

    Reflex cannot nest a filtered `foreach`, so the screen walks one flat list and
    each row says which job it belongs to (see `WizardState._flatten_for_ui`).
    """
    rows: list[dict[str, str]] = []
    for experience in profile.experiences:
        rows.append(
            _row(
                row="job",
                key=experience.id,
                experience_id=experience.id,
                role=experience.role,
                company=experience.company,
                dates=experience.period(),
                count=_count(len(experience.achievements)),
            )
        )
        last = len(experience.achievements) - 1
        rows += [
            _row(
                row="achievement",
                key=f"{experience.id}|{achievement.id}",
                experience_id=experience.id,
                achievement_id=achievement.id,
                text=achievement.text,
                origin=str(origin_of(achievement)),
                linkedin_text=achievement.imported_value or "",
                # Text and not bool: the whole list is dict[str, str] for Reflex.
                first="yes" if index == 0 else "",
                last="yes" if index == last else "",
            )
            for index, achievement in enumerate(experience.achievements)
        ]
        rows.append(_row(row="add", key=f"{experience.id}|add", experience_id=experience.id))
    return rows


def _ids_of(key: str) -> tuple[str, str]:
    """The job and achievement ids of a row key.

    The key comes from the browser. One without the separator leaves an empty
    achievement id, and the services reject it with their clear error.
    """
    experience_id, _, achievement_id = key.partition("|")
    return experience_id, achievement_id


class ExperienceState(rx.State):
    """Edits the achievements of each job of the master profile."""

    has_profile: bool = False
    rows: list[dict[str, str]] = []
    # Unfolded jobs, by experience id. A profile with eight jobs would be one long scroll.
    open_jobs: dict[str, bool] = {}

    # Only one form is open at a time: the editor of an achievement (by row key), the
    # add form of a job (by experience id) or a delete confirmation (by row key).
    editing_key: str = ""
    adding_to: str = ""
    confirming_key: str = ""

    error: str = ""
    # Part of the editor's `key`. It goes up with every operation, so a rejected text
    # shows the saved one again instead of keeping what you typed.
    version: int = 0

    @rx.event
    def start(self) -> None:
        """Loads the profile from disk with the first job open and the rest folded."""
        self._close_forms()
        self.error = ""

        profile = load_profile(DATA_DIR)
        self.has_profile = profile is not None
        if profile is None:
            self.rows = []
            self.open_jobs = {}
            return

        self.rows = achievement_rows(profile)
        self.open_jobs = {experience.id: index == 0 for index, experience in enumerate(profile.experiences)}

    def _close_forms(self) -> None:
        self.editing_key = ""
        self.adding_to = ""
        self.confirming_key = ""

    def _show(self, profile: MasterProfile) -> None:
        """Rebuilds the rows and keeps folded what was folded. A job new to this screen comes in folded."""
        self.rows = achievement_rows(profile)
        self.open_jobs = {experience.id: self.open_jobs.get(experience.id, False) for experience in profile.experiences}

    async def _change(self, operation: Callable[[MasterProfile], MasterProfile]) -> None:
        """Applies an operation on the achievements and saves it right away.

        It starts from the profile on disk and not from the one loaded when the screen
        opened: if you synced in another tab in the meantime, saving the old one would
        erase that.
        """
        self.error = ""
        self.version += 1
        on_disk: MasterProfile | None = None
        try:
            on_disk = await asyncio.to_thread(load_profile, DATA_DIR)
            if on_disk is None:
                raise ValueError("There is no profile yet. Sync with LinkedIn first.")
            updated = operation(on_disk)
            await asyncio.to_thread(save_profile, DATA_DIR, updated)
        except (ValueError, OSError) as error:
            self.error = str(error)
            # Nothing was saved, but the screen may be the stale one: after "That achievement
            # no longer exists" it would keep offering the row that fails.
            if on_disk is not None:
                self._show(on_disk)
            return

        self._show(updated)
        self._close_forms()

    # ------------------------------------------------------------------ jobs

    @rx.event
    def toggle_job(self, experience_id: str) -> None:
        # The id comes from the browser: only a job on screen can be folded or unfolded.
        if experience_id in self.open_jobs:
            self.open_jobs[experience_id] = not self.open_jobs[experience_id]

    # ------------------------------------------------------------------ edit

    @rx.event
    def start_edit(self, key: str) -> None:
        self._close_forms()
        self.error = ""
        self.editing_key = key

    @rx.event
    def cancel_edit(self) -> None:
        self.editing_key = ""
        self.error = ""

    @rx.event
    async def save_edit(self, data: dict[str, Any]) -> None:
        """The achievement comes from `editing_key` and not from the form: Reflex compiles the
        `on_submit` outside the `foreach`, where the row does not exist."""
        # A second click on Save arrives once the first one closed the editor.
        if not self.editing_key:
            return
        experience_id, achievement_id = _ids_of(self.editing_key)
        text = str(data.get("text", ""))
        await self._change(
            lambda profile: achievement_operations.edit_achievement(profile, experience_id, achievement_id, text)
        )

    @rx.event
    async def restore(self, key: str) -> None:
        experience_id, achievement_id = _ids_of(key)
        await self._change(
            lambda profile: achievement_operations.restore_linkedin_text(profile, experience_id, achievement_id)
        )

    # ------------------------------------------------------- duplicate and move

    @rx.event
    async def duplicate(self, key: str) -> None:
        experience_id, achievement_id = _ids_of(key)
        await self._change(
            lambda profile: achievement_operations.duplicate_achievement(profile, experience_id, achievement_id)
        )

    @rx.event
    async def move(self, key: str, offset: int) -> None:
        # The buttons only send one step; anything else did not come from them.
        if offset not in (-1, 1):
            return
        experience_id, achievement_id = _ids_of(key)
        await self._change(
            lambda profile: achievement_operations.move_achievement(profile, experience_id, achievement_id, offset)
        )

    # ------------------------------------------------------------------ delete

    @rx.event
    def ask_delete(self, key: str) -> None:
        self._close_forms()
        self.error = ""
        self.confirming_key = key

    @rx.event
    def cancel_delete(self) -> None:
        self.confirming_key = ""
        self.error = ""

    @rx.event
    async def confirm_delete(self, key: str) -> None:
        experience_id, achievement_id = _ids_of(key)
        await self._change(
            lambda profile: achievement_operations.remove_achievement(profile, experience_id, achievement_id)
        )

    # --------------------------------------------------------------------- add

    @rx.event
    def start_add(self, experience_id: str) -> None:
        self._close_forms()
        self.error = ""
        self.adding_to = experience_id

    @rx.event
    def cancel_add(self) -> None:
        self.adding_to = ""
        self.error = ""

    @rx.event
    async def add(self, data: dict[str, Any]) -> None:
        """The job comes from `adding_to`, for the same reason as in `save_edit`."""
        if not self.adding_to:
            return
        experience_id = self.adding_to
        text = str(data.get("text", ""))
        await self._change(lambda profile: achievement_operations.add_achievement(profile, experience_id, text))

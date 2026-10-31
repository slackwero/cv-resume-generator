"""State of the Work experience subsection of My profile.

The owner edits, duplicates, adds, removes and reorders the achievements of each job.
The jobs themselves (role, company, dates) come from LinkedIn and are read-only here.
Every operation saves right away, like the skills.
"""

import asyncio
import json
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


def focus_after_delete(rows: list[dict[str, str]], key: str) -> str:
    """Where the keyboard goes once an achievement is deleted, worked out from the rows before.

    To the achievement that takes its place, the one above when it was the last, and the
    job's add button when it was the only one. Empty when the row is not listed.
    """
    index = next((i for i, row in enumerate(rows) if row["key"] == key), None)
    if index is None or rows[index]["row"] != "achievement":
        return ""
    # A job's achievements are always followed by its add row and preceded by its heading.
    for neighbour in (rows[index + 1], rows[index - 1]):
        if neighbour["row"] == "achievement":
            return f"edit-{neighbour['key']}"
    return f"add-{rows[index]['experience_id']}"


def focus_after_move(rows: list[dict[str, str]], key: str, offset: int) -> str:
    """The arrow to keep the keyboard on after a move, worked out from the rows after it.

    The same arrow, so pressing it again keeps moving; the other one once the achievement
    reached that end, because the first one is disabled there.
    """
    row = next((row for row in rows if row["key"] == key), None)
    if row is None:
        return ""
    if row["first"] and row["last"]:
        return f"edit-{key}"
    at_the_end = row["last"] if offset == 1 else row["first"]
    going_down = (offset == 1) != bool(at_the_end)
    return f"move-{'down' if going_down else 'up'}-{key}"


def _focus(element_id: str) -> rx.event.EventSpec | None:
    """Puts the keyboard on a control once the screen has redrawn.

    Closing a form or moving a row takes the focused button out of the page, and the
    browser drops the focus to the top of it: a keyboard user would have to start over.
    Two frames, because the change arrives before React draws it.
    """
    if not element_id:
        return None
    target = json.dumps(element_id)
    return rx.call_script(
        f"requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById({target})?.focus()))"
    )


def _same_text(typed: str, saved: str) -> bool:
    """Whether saving `typed` would leave `saved` as it is: saving trims it, and a textarea
    turns the CRLF of an imported text into LF."""
    return typed.replace("\r\n", "\n").strip() == saved.replace("\r\n", "\n").strip()


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
    # What you typed in a form and did not send, by row key: an achievement's, or a job's
    # add row. Clicking another achievement or folding the job closes the form, not what
    # you wrote in it; only Cancel throws it away.
    drafts: dict[str, str] = {}

    error: str = ""
    # The row whose action failed, where the error shows: inside its open form, next to
    # its buttons, or under it for move and duplicate. Empty when that row is gone, and
    # the error shows above the list.
    error_at: str = ""

    @rx.event
    def start(self) -> None:
        """Loads the profile from disk.

        The first time, the first job opens and the rest fold. After that, it runs again
        on Back from another subsection and on a reload: what you folded stays folded.
        """
        self._close_forms()
        self._clear_error()

        profile = load_profile(DATA_DIR)
        self.has_profile = profile is not None
        if profile is None:
            self.rows = []
            self.open_jobs = {}
            return

        first_visit = not self.open_jobs
        self._show(profile)
        if first_visit:
            self.open_jobs = {experience.id: index == 0 for index, experience in enumerate(profile.experiences)}

    def _close_forms(self) -> None:
        self.editing_key = ""
        self.adding_to = ""
        self.confirming_key = ""

    def _clear_error(self) -> None:
        self.error = ""
        self.error_at = ""

    def _show(self, profile: MasterProfile) -> None:
        """Rebuilds the rows and keeps folded what was folded. A job new to this screen comes in folded.

        The draft of a row that is gone goes with it.
        """
        self.rows = achievement_rows(profile)
        self.open_jobs = {experience.id: self.open_jobs.get(experience.id, False) for experience in profile.experiences}
        keys = {row["key"] for row in self.rows}
        self.drafts = {key: text for key, text in self.drafts.items() if key in keys}

    async def _change(self, operation: Callable[[MasterProfile], MasterProfile], *, at: str) -> bool:
        """Applies an operation on the achievements and saves it right away. Returns whether it saved.

        It starts from the profile on disk and not from the one loaded when the screen
        opened: if you synced in another tab in the meantime, saving the old one would
        erase that. `at` is the row the action came from, where its error shows.
        """
        self._clear_error()
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
            self.error_at = at if any(row["key"] == at for row in self.rows) else ""
            return False

        self._show(updated)
        return True

    # ------------------------------------------------------------------ jobs

    @rx.event
    def toggle_job(self, experience_id: str) -> None:
        # The id comes from the browser: only a job on screen can be folded or unfolded.
        if experience_id in self.open_jobs:
            self.open_jobs[experience_id] = not self.open_jobs[experience_id]

    # ---------------------------------------------------------------- drafts

    @rx.event
    def keep_draft(self, key: str, text: str) -> None:
        """What you typed: when you leave the field, and a moment after you stop typing.

        Leaving the field arrives before the click that takes you elsewhere. The pause
        covers what leaves no field behind: Back with a gesture, or a reload. That one
        may land after Cancel or Save, so only the form still open takes it. Typing the
        saved text back, or nothing in a new one, is no draft.
        """
        open_form = self.editing_key if self.editing_key else f"{self.adding_to}|add"
        row = next((row for row in self.rows if row["key"] == key), None)
        if row is None or key != open_form:
            return
        unchanged = _same_text(text, row["text"]) if row["row"] == "achievement" else not text.strip()
        if unchanged:
            self.drafts.pop(key, None)
        else:
            self.drafts[key] = text

    # ------------------------------------------------------------------ edit

    @rx.event
    def start_edit(self, key: str) -> None:
        self._close_forms()
        self._clear_error()
        self.editing_key = key

    @rx.event
    def cancel_edit(self) -> rx.event.EventSpec | None:
        key = self.editing_key
        self.editing_key = ""
        self.drafts.pop(key, None)
        self._clear_error()
        return _focus(f"edit-{key}")

    @rx.event
    async def save_edit(self, data: dict[str, Any]) -> rx.event.EventSpec | None:
        """The achievement comes from `editing_key` and not from the form: Reflex compiles the
        `on_submit` outside the `foreach`, where the row does not exist."""
        # A second click on Save arrives once the first one closed the editor.
        if not self.editing_key:
            return None
        key = self.editing_key
        experience_id, achievement_id = _ids_of(key)
        text = str(data.get("text", ""))
        saved = await self._change(
            lambda profile: achievement_operations.edit_achievement(profile, experience_id, achievement_id, text),
            at=key,
        )
        return self._close_editor(key) if saved else None

    @rx.event
    async def restore(self, key: str) -> rx.event.EventSpec | None:
        # The button lives in the open editor, which closes with LinkedIn's text back.
        experience_id, achievement_id = _ids_of(key)
        saved = await self._change(
            lambda profile: achievement_operations.restore_linkedin_text(profile, experience_id, achievement_id),
            at=key,
        )
        return self._close_editor(key) if saved else None

    def _close_editor(self, key: str) -> rx.event.EventSpec | None:
        self.editing_key = ""
        self.drafts.pop(key, None)
        return _focus(f"edit-{key}")

    # ------------------------------------------------------- duplicate and move

    @rx.event
    async def duplicate(self, key: str) -> None:
        # An open form stays open: the copy goes in below the original, away from it.
        experience_id, achievement_id = _ids_of(key)
        await self._change(
            lambda profile: achievement_operations.duplicate_achievement(profile, experience_id, achievement_id),
            at=key,
        )

    @rx.event
    async def move(self, key: str, offset: int) -> rx.event.EventSpec | None:
        # The buttons only send one step; anything else did not come from them.
        if offset not in (-1, 1):
            return None
        experience_id, achievement_id = _ids_of(key)
        moved = await self._change(
            lambda profile: achievement_operations.move_achievement(profile, experience_id, achievement_id, offset),
            at=key,
        )
        return _focus(focus_after_move(self.rows, key, offset)) if moved else None

    # ------------------------------------------------------------------ delete

    @rx.event
    def ask_delete(self, key: str) -> None:
        self._close_forms()
        self._clear_error()
        self.confirming_key = key

    @rx.event
    def cancel_delete(self) -> rx.event.EventSpec | None:
        key = self.confirming_key
        self.confirming_key = ""
        self._clear_error()
        return _focus(f"delete-{key}")

    @rx.event
    async def confirm_delete(self, key: str) -> rx.event.EventSpec | None:
        """Only the achievement whose question is open: the confirmation is required here
        and not only on screen, and a second click on Delete arrives once it is gone."""
        if not key or key != self.confirming_key:
            return None
        target = focus_after_delete(self.rows, key)
        experience_id, achievement_id = _ids_of(key)
        deleted = await self._change(
            lambda profile: achievement_operations.remove_achievement(profile, experience_id, achievement_id),
            at=key,
        )
        if not deleted:
            return None
        self.confirming_key = ""
        return _focus(target)

    # --------------------------------------------------------------------- add

    @rx.event
    def start_add(self, experience_id: str) -> None:
        self._close_forms()
        self._clear_error()
        self.adding_to = experience_id

    @rx.event
    def cancel_add(self) -> rx.event.EventSpec | None:
        experience_id = self.adding_to
        self.adding_to = ""
        self.drafts.pop(f"{experience_id}|add", None)
        self._clear_error()
        return _focus(f"add-{experience_id}")

    @rx.event
    async def add(self, data: dict[str, Any]) -> rx.event.EventSpec | None:
        """The job comes from `adding_to`, for the same reason as in `save_edit`."""
        if not self.adding_to:
            return None
        experience_id = self.adding_to
        text = str(data.get("text", ""))
        added = await self._change(
            lambda profile: achievement_operations.add_achievement(profile, experience_id, text),
            at=f"{experience_id}|add",
        )
        if not added:
            return None
        self.adding_to = ""
        self.drafts.pop(f"{experience_id}|add", None)
        return _focus(f"add-{experience_id}")

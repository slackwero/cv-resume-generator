"""State of the Work experience subsection of My profile.

The owner edits, duplicates, adds, removes and reorders the achievements of each job, in
the language My profile shows. The jobs themselves (company, dates) come from LinkedIn
and are read-only here. Their role and location are read-only too in the source
language, which LinkedIn feeds, and are translated by hand in the other one. Every
operation saves right away, like the skills.
"""

import asyncio
from collections.abc import Callable
from typing import Any, TypedDict

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.app.errors import as_sentence
from cv_generator.app.focus import focus_on
from cv_generator.app.states.profile_state import ProfileState, text_version
from cv_generator.models.profile import Experience, MasterProfile
from cv_generator.rendering.i18n import language_name
from cv_generator.services import achievements as achievement_operations
from cv_generator.services.achievements import origin_of
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import TextState, save_translation, source_text_of, text_key
from cv_generator.services.translations import confirm as confirm_version

# The texts of a job that have a version per language, with their label on screen.
JOB_FIELDS: dict[str, str] = {"role": "Role", "location": "Location"}

# What an achievement row takes from `text_version`. Its `key` is the row's own.
_ACHIEVEMENT_VERSION = ("text", "own", "state", "reference", "reference_language")


class ExperienceRow(TypedDict):
    """One row of the flat list: a job, one of its achievements or its add row.

    Every row carries every key: `rx.foreach` walks a single type and does not like some
    rows carrying keys others do not. A TypedDict and not `dict[str, str]`, because a
    job's role and location are rows of their own, the ones `translation_field` takes.
    """

    row: str
    key: str
    experience_id: str
    achievement_id: str
    company: str
    dates: str
    count: str
    # The achievement as `text_version` shows it in the language on screen.
    text: str
    own: str
    state: str
    reference: str
    reference_language: str
    origin: str
    linkedin_text: str
    first: str
    last: str
    # The job's role and location as `text_version` shows them, with their `label` and
    # whether they are `editable`. Empty in the other rows.
    role: dict[str, str]
    location: dict[str, str]


ROW_KEYS = tuple(ExperienceRow.__annotations__)

# What a write returns: where the keyboard goes, if anywhere, and the menu counts read
# again from disk, since the write may have changed what is pending.
WriteEvents = list[rx.event.EventSpec | rx.event.EventHandler]


def _row(**values: str | dict[str, str]) -> ExperienceRow:
    return ExperienceRow(**{**dict.fromkeys(ROW_KEYS, ""), "role": {}, "location": {}, **values})


def _counted(*events: rx.event.EventSpec | None) -> WriteEvents:
    return [*(event for event in events if event is not None), ProfileState.refresh_counts]


def _count(total: int) -> str:
    if total == 0:
        return "No achievements"
    if total == 1:
        return "1 achievement"
    return f"{total} achievements"


def _job_texts(profile: MasterProfile, experience: Experience, language: str) -> dict[str, dict[str, str]]:
    """The role and location of a job in `language`.

    They are editable in the other language only, and only when the source has text: in
    the source language LinkedIn writes them, and a text in the other language alone
    would stay pending in the source one, where nothing writes it by hand.
    """
    in_source = language == profile.source_language
    return {
        field: {
            **text_version(profile, language, text_key(experience.id, field)),
            "label": label,
            "editable": "yes" if not in_source and getattr(experience, field) else "",
        }
        for field, label in JOB_FIELDS.items()
    }


def achievement_rows(profile: MasterProfile, language: str) -> list[ExperienceRow]:
    """Each job, its achievements and its add row, flattened in profile order, in `language`.

    Reflex cannot nest a filtered `foreach`, so the screen walks one flat list and
    each row says which job it belongs to (see `WizardState._flatten_for_ui`). A text
    missing in `language` shows the other language's, as `text_version` says.
    """
    rows: list[ExperienceRow] = []
    for experience in profile.experiences:
        rows.append(
            _row(
                row="job",
                key=experience.id,
                experience_id=experience.id,
                company=experience.company,
                dates=experience.period(),
                count=_count(len(experience.achievements)),
                **_job_texts(profile, experience, language),
            )
        )
        last = len(experience.achievements) - 1
        for index, achievement in enumerate(experience.achievements):
            version = text_version(profile, language, text_key(achievement.id, "text"))
            rows.append(
                _row(
                    row="achievement",
                    key=f"{experience.id}|{achievement.id}",
                    experience_id=experience.id,
                    achievement_id=achievement.id,
                    **{field: version[field] for field in _ACHIEVEMENT_VERSION},
                    # Where the achievement stands against LinkedIn, whatever the language:
                    # the delete question says it too.
                    origin=str(origin_of(achievement)),
                    linkedin_text=achievement.imported_value or "",
                    # Text and not bool: Reflex walks these as text.
                    first="yes" if index == 0 else "",
                    last="yes" if index == last else "",
                )
            )
        rows.append(_row(row="add", key=f"{experience.id}|add", experience_id=experience.id))
    return rows


def focus_after_delete(rows: list[ExperienceRow], key: str) -> str:
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


def focus_after_move(rows: list[ExperienceRow], key: str, offset: int) -> str:
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
    """Edits the achievements of each job of the master profile, and translates its role and location."""

    has_profile: bool = False
    rows: list[ExperienceRow] = []
    # Unfolded jobs, by experience id. A profile with eight jobs would be one long scroll.
    open_jobs: dict[str, bool] = {}

    # The language the achievements are shown and edited in, always the one the rest of
    # My profile shows (`ProfileState.language`); and the one LinkedIn feeds.
    language: str = ""
    source_language: str = ""

    # Only one form is open at a time: the editor of an achievement (by row key), the
    # add form of a job (by experience id) or a delete confirmation (by row key).
    editing_key: str = ""
    adding_to: str = ""
    confirming_key: str = ""
    # What you typed in a form and did not send, by row key: an achievement's, or a job's
    # add row. Clicking another achievement or folding the job closes the form, not what
    # you wrote in it; only Cancel throws it away.
    drafts: dict[str, str] = {}
    # The drafts typed in a language that is not on screen, by language. Flipping the
    # switch never carries them into the other language's forms.
    held_drafts: dict[str, dict[str, str]] = {}

    error: str = ""
    # The row whose action failed, where the error shows: inside its open form, next to
    # its buttons, or under it for move and duplicate. Empty when that row is gone, and
    # the error shows above the list.
    error_at: str = ""

    @rx.event
    async def start(self) -> None:
        """Loads the profile from disk, in the language the rest of My profile shows.

        The first time, the first job opens and the rest fold. After that, it runs again
        on Back from another subsection and on a reload: what you folded stays folded.

        It runs after `ProfileState.start` in the page's on_load, and takes the language
        from it instead of reading the remembered one: after a switch that could not be
        remembered, the file holds the language before it.
        """
        self._close_forms()
        self._clear_error()
        self._move_to(await self._screen_language())

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

    @rx.event
    async def show_language(self) -> None:
        """Follows the switch, which `ProfileState.switch_language` handles first in the same click.

        The open form closes. What you typed in it stays with the language it was typed in.
        """
        language = await self._screen_language()
        if language == self.language:
            return
        self._close_forms()
        self._clear_error()
        self._move_to(language)
        profile = load_profile(DATA_DIR)
        if profile is not None:
            self._show(profile)

    async def _screen_language(self) -> str:
        return (await self.get_state(ProfileState)).language

    def _move_to(self, code: str) -> None:
        """Puts the editor in another language: the drafts on screen are held in the one
        they were typed in, and the ones held for `code` come back."""
        if code == self.language:
            return
        held = dict(self.held_drafts)
        if self.drafts:
            held[self.language] = dict(self.drafts)
        self.drafts = held.pop(code, {})
        self.held_drafts = held
        self.language = code

    @rx.var
    def held_draft_languages(self) -> dict[str, str]:
        """The rows with something typed and not sent in a language not on screen, with the
        codes of those languages as Contact names them ("EN")."""
        codes: dict[str, list[str]] = {}
        for code in sorted(self.held_drafts):
            for key in self.held_drafts[code]:
                codes.setdefault(key, []).append(code.upper())
        return {key: ", ".join(found) for key, found in codes.items()}

    @rx.var
    def in_source(self) -> bool:
        """Whether the language on screen is the one LinkedIn feeds: only there do the
        LinkedIn tag, its text and Restore apply."""
        return self.language == self.source_language

    def _close_forms(self) -> None:
        self.editing_key = ""
        self.adding_to = ""
        self.confirming_key = ""

    def _clear_error(self) -> None:
        self.error = ""
        self.error_at = ""

    def _show(self, profile: MasterProfile) -> None:
        """Rebuilds the rows and keeps folded what was folded. A job new to this screen comes in folded.

        The draft of a row that is gone goes with it, in every language.
        """
        self.source_language = profile.source_language or ""
        self.rows = achievement_rows(profile, self.language)
        self.open_jobs = {experience.id: self.open_jobs.get(experience.id, False) for experience in profile.experiences}
        keys = {row["key"] for row in self.rows}
        self.drafts = {key: text for key, text in self.drafts.items() if key in keys}
        held: dict[str, dict[str, str]] = {}
        for code, drafts in self.held_drafts.items():
            kept = {key: text for key, text in drafts.items() if key in keys}
            if kept:
                held[code] = kept
        self.held_drafts = held

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
            self.error = as_sentence(error)
            # Nothing was saved, but the screen may be the stale one: after "That achievement
            # no longer exists" it would keep offering the row that fails.
            if on_disk is not None:
                self._show(on_disk)
            self.error_at = at if any(row["key"] == at for row in self.rows) else ""
            return False

        self._show(updated)
        return True

    def _row_of(self, key: str) -> ExperienceRow | None:
        return next((row for row in self.rows if row["key"] == key), None)

    # ------------------------------------------------------------------ jobs

    @rx.event
    def toggle_job(self, experience_id: str) -> None:
        # The id comes from the browser: only a job on screen can be folded or unfolded.
        if experience_id in self.open_jobs:
            self.open_jobs[experience_id] = not self.open_jobs[experience_id]

    def _job_text(self, key: str) -> tuple[ExperienceRow, dict[str, str]] | None:
        """The job and its role or location on screen under this key, or None. The key comes
        from the browser, so it is looked up among the rows and never used to build anything."""
        return next(
            (
                (row, row[field])
                for row in self.rows
                if row["row"] == "job"
                for field in JOB_FIELDS
                if row[field]["key"] == key
            ),
            None,
        )

    async def _save_job_field(self, key: str, text: str) -> WriteEvents | None:
        """Role or location in the other language. In the source one LinkedIn writes them:
        their row is not editable there.

        It arrives twice per edit, on Enter and when leaving the field: if the text did not
        change, it does nothing.
        """
        found = self._job_text(key)
        if found is None:
            return None
        job, version = found
        if version["editable"] != "yes":
            self.error = f"The {language_name(self.source_language)} text comes from LinkedIn and is changed there."
            self.error_at = job["key"]
            return None
        if text.strip() == version["own"]:
            return None
        language = self.language
        await self._change(lambda profile: save_translation(profile, language, key, text), at=job["key"])
        return _counted()

    @rx.event
    async def save_job_field(self, key: str, text: str) -> WriteEvents | None:
        """When leaving the field."""
        return await self._save_job_field(key, text)

    @rx.event
    async def job_field_from_form(self, data: dict[str, Any]) -> WriteEvents | None:
        """When pressing Enter."""
        return await self._save_job_field(str(data.get("key", "")), str(data.get("text", "")))

    @rx.event
    async def confirm_job_field(self, key: str) -> WriteEvents | None:
        """ "Still good" on a role or location pending review, in either language."""
        found = self._job_text(key)
        if found is None or found[1]["state"] != TextState.REVIEW:
            return None
        language = self.language
        await self._change(lambda profile: confirm_version(profile, language, key), at=found[0]["key"])
        return _counted()

    @rx.event
    async def same_job_field(self, key: str) -> WriteEvents | None:
        """ "Use the same text": the source text becomes this language's, saved right away."""
        found = self._job_text(key)
        if found is None or found[1]["copyable"] != "yes":
            return None
        language = self.language
        await self._change(
            lambda profile: save_translation(profile, language, key, source_text_of(profile, key)),
            at=found[0]["key"],
        )
        return _counted()

    # ---------------------------------------------------------------- drafts

    @rx.event
    def keep_draft(self, key: str, text: str) -> None:
        """What you typed: when you leave the field, and a moment after you stop typing.

        Leaving the field arrives before the click that takes you elsewhere. The pause
        covers what leaves no field behind: Back with a gesture, or a reload. That one
        may land after Cancel or Save, so only the form still open takes it. Typing the
        saved text back, or nothing in a new one, is no draft. The saved text is this
        language's own: while it is missing, the other language's text shown in its place
        is not what the editor started from.
        """
        open_form = self.editing_key if self.editing_key else f"{self.adding_to}|add"
        row = self._row_of(key)
        if row is None or key != open_form:
            return
        unchanged = _same_text(text, row["own"]) if row["row"] == "achievement" else not text.strip()
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
        return focus_on(f"edit-{key}")

    @rx.event
    async def save_edit(self, data: dict[str, Any]) -> WriteEvents | None:
        """The achievement comes from `editing_key` and not from the form: Reflex compiles the
        `on_submit` outside the `foreach`, where the row does not exist.

        In the source language it changes the achievement; in the other one it writes that
        language's text and leaves the source one as it is.
        """
        # A second click on Save arrives once the first one closed the editor.
        if not self.editing_key:
            return None
        key = self.editing_key
        experience_id, achievement_id = _ids_of(key)
        text = str(data.get("text", ""))
        language = self.language
        saved = await self._change(
            lambda profile: achievement_operations.edit_achievement_in(
                profile, experience_id, achievement_id, text, language
            ),
            at=key,
        )
        return _counted(self._close_editor(key) if saved else None)

    @rx.event
    async def restore(self, key: str) -> WriteEvents | None:
        """Only in the source language: LinkedIn's text is that language's.

        The button lives in the open editor, which closes with LinkedIn's text back.
        """
        if self.language != self.source_language:
            return None
        experience_id, achievement_id = _ids_of(key)
        saved = await self._change(
            lambda profile: achievement_operations.restore_linkedin_text(profile, experience_id, achievement_id),
            at=key,
        )
        return _counted(self._close_editor(key) if saved else None)

    def _close_editor(self, key: str) -> rx.event.EventSpec | None:
        self.editing_key = ""
        self.drafts.pop(key, None)
        return focus_on(f"edit-{key}")

    @rx.event
    async def confirm(self, key: str) -> WriteEvents | None:
        """ "Still good" on an achievement pending review, in either language: it is current
        again, as it is."""
        row = self._row_of(key)
        if row is None or row["row"] != "achievement" or row["state"] != TextState.REVIEW:
            return None
        language, text = self.language, text_key(row["achievement_id"], "text")
        await self._change(lambda profile: confirm_version(profile, language, text), at=key)
        return _counted()

    # ------------------------------------------------------- duplicate and move

    @rx.event
    async def duplicate(self, key: str) -> WriteEvents:
        # An open form stays open: the copy goes in below the original, away from it.
        experience_id, achievement_id = _ids_of(key)
        await self._change(
            lambda profile: achievement_operations.duplicate_achievement(profile, experience_id, achievement_id),
            at=key,
        )
        return _counted()

    @rx.event
    async def move(self, key: str, offset: int) -> WriteEvents | None:
        # The buttons only send one step; anything else did not come from them.
        if offset not in (-1, 1):
            return None
        experience_id, achievement_id = _ids_of(key)
        moved = await self._change(
            lambda profile: achievement_operations.move_achievement(profile, experience_id, achievement_id, offset),
            at=key,
        )
        return _counted(focus_on(focus_after_move(self.rows, key, offset)) if moved else None)

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
        return focus_on(f"delete-{key}")

    @rx.event
    async def confirm_delete(self, key: str) -> WriteEvents | None:
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
            return _counted()
        self.confirming_key = ""
        return _counted(focus_on(target))

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
        return focus_on(f"add-{experience_id}")

    @rx.event
    async def add(self, data: dict[str, Any]) -> WriteEvents | None:
        """The job comes from `adding_to`, for the same reason as in `save_edit`.

        Added in the other language, the achievement has that language's text and no
        source one yet: it is pending translation there.
        """
        if not self.adding_to:
            return None
        experience_id = self.adding_to
        text = str(data.get("text", ""))
        language = self.language
        added = await self._change(
            lambda profile: achievement_operations.add_achievement_in(profile, experience_id, text, language),
            at=f"{experience_id}|add",
        )
        if not added:
            return _counted()
        self.adding_to = ""
        self.drafts.pop(f"{experience_id}|add", None)
        return _counted(focus_on(f"add-{experience_id}"))

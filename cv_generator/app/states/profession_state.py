"""State of the list of professions in My profile → Contact.

Each entry is a complete headline with a version per language, edited in both. Every
change saves right away, the way the skills and achievements do, and not through
Contact's Save button.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.app.errors import as_sentence, readable
from cv_generator.app.focus import focus_on
from cv_generator.app.states.profile_state import ProfileState, text_version
from cv_generator.models.profile import MasterProfile
from cv_generator.services import professions as operations
from cv_generator.services.placeholders import is_usable_text
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import TextState, text_key
from cv_generator.services.translations import confirm as confirm_version

# What a write returns: the menu counts and the "What the CV needs" status read again from
# disk, since the write may have changed them.
WriteEvents = list[rx.event.EventSpec | rx.event.EventHandler]

# Where an error of the add form shows: no row has this key.
ADD_FORM = "add"


def profession_rows(profile: MasterProfile, language: str) -> list[dict[str, str]]:
    """The headlines as rows of `translation_field`, in order, in `language`.

    The row is `text_version` of the entry's `<id>.text`, plus:

    - `id`, `label` and `editable`: every version is editable, in both languages;
    - `first` and `last`, for the arrows;
    - `copyable` "yes" on a missing version when the other has text: headlines are short
      and often identical, so "Use the same text" works from either language.

    The importer's placeholder is not a headline: it shows as empty, so nobody has to
    delete the word before typing.
    """
    last = len(profile.professions) - 1
    rows: list[dict[str, str]] = []
    for index, profession in enumerate(profile.professions):
        row = text_version(profile, language, text_key(profession.id, "text"))
        usable = {field: row[field] if is_usable_text(row[field]) else "" for field in ("text", "own", "reference")}
        rows.append(
            {
                **row,
                **usable,
                "copyable": "yes" if row["state"] == TextState.MISSING and usable["text"] else "",
                "id": profession.id,
                "label": "Profession",
                "editable": "yes",
                "first": "yes" if index == 0 else "",
                "last": "yes" if index == last else "",
            }
        )
    return rows


def _focus_after_move(rows: list[dict[str, str]], key: str, offset: int) -> str:
    """The arrow to keep the keyboard on after a move, worked out from the rows after it:
    the same one, so pressing it again keeps moving, and the other once it reached the end."""
    row = next((row for row in rows if row["key"] == key), None)
    if row is None:
        return ""
    if row["first"] and row["last"]:
        return f"translation-{key}"
    at_the_end = row["last"] if offset == 1 else row["first"]
    going_down = (offset == 1) != bool(at_the_end)
    return f"profession-move-{'down' if going_down else 'up'}-{key}"


def _focus_after_delete(rows: list[dict[str, str]], key: str) -> str:
    """The field of the entry that takes its place, the one above when it was the last."""
    index = next((i for i, row in enumerate(rows) if row["key"] == key), None)
    if index is None or len(rows) < 2:
        return ""
    neighbour = rows[index + 1] if index + 1 < len(rows) else rows[index - 1]
    return f"translation-{neighbour['key']}"


class ProfessionState(rx.State):
    """Adds, edits, reorders and deletes the headlines of the master profile."""

    rows: list[dict[str, str]] = []
    # The language the list is shown in, always the one the rest of My profile shows
    # (`ProfileState.language`); and the one LinkedIn feeds.
    language: str = ""
    source_language: str = ""
    error: str = ""
    # Where the error shows: a row key, `ADD_FORM`, or empty for the whole list.
    error_at: str = ""
    # The row whose delete question is open.
    confirming_key: str = ""

    @rx.event
    async def start(self) -> None:
        """Loads the profile from disk, in the language the rest of My profile shows.

        It runs after `ProfileState.start` in the page's on_load and takes the language
        from it: after a switch that could not be remembered, the file holds the one before.
        """
        self.language = await self._screen_language()
        self.confirming_key = ""
        await self._reload()

    @rx.event
    async def show_language(self) -> None:
        """Follows the switch, which `ProfileState.switch_language` handles first in the same click."""
        language = await self._screen_language()
        if language == self.language:
            return
        self.language = language
        self.confirming_key = ""
        await self._reload()

    async def _screen_language(self) -> str:
        return (await self.get_state(ProfileState)).language

    async def _reload(self) -> None:
        """Shows the profile on disk. One that cannot be read shows as an error, not a crash."""
        self._clear_error()
        try:
            profile = await asyncio.to_thread(load_profile, DATA_DIR)
        except (ValueError, OSError) as error:
            self.error = f"Your profile could not be read: {readable(error)}"
            profile = None
        self._show(profile)

    def _clear_error(self) -> None:
        self.error = ""
        self.error_at = ""

    def _show(self, profile: MasterProfile | None) -> None:
        if profile is None:
            self.source_language = ""
            self.rows = []
            return
        self.source_language = profile.source_language or ""
        self.rows = profession_rows(profile, self.language)

    def _row_of(self, key: str) -> dict[str, str] | None:
        """The row on screen under this key, or None. The key comes from the browser, so it
        is looked up among the rows and never used to build anything."""
        return next((row for row in self.rows if row["key"] == key), None)

    async def _change(self, operation: Callable[[MasterProfile], MasterProfile], *, at: str) -> bool:
        """Applies an operation and saves it right away; False when it failed.

        It starts from the profile on disk and not from the one loaded when the screen
        opened: if you synced in another tab in the meantime, saving the old one would
        erase that. `at` is where an error shows.
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
            # Nothing was saved, but the screen may be the stale one: after "That profession
            # no longer exists" it would keep offering the row that fails. A profile that
            # cannot be read leaves the list as it is.
            if on_disk is not None:
                self._show(on_disk)
            # An error of a row that is gone shows above the list.
            self.error_at = at if at == ADD_FORM or any(row["key"] == at for row in self.rows) else ""
            return False
        self._show(updated)
        return True

    # --------------------------------------------------------------------- add

    @rx.event
    async def add(self, data: dict[str, Any]) -> WriteEvents | None:
        """Adds a headline at the end, written in the language on screen."""
        text, language = str(data.get("text", "")), self.language
        added = await self._change(lambda profile: operations.add_profession(profile, text, language), at=ADD_FORM)
        return [ProfileState.refresh_counts] if added else None

    # -------------------------------------------------------------------- edit

    async def _save(self, key: str, text: str) -> WriteEvents | None:
        """The headline in the language on screen.

        It arrives twice per edit, on Enter and when leaving the field: if the text did not
        change, it does nothing.
        """
        row = self._row_of(key)
        if row is None or text.strip() == row["own"]:
            return None
        profession_id, language = row["id"], self.language
        await self._change(lambda profile: operations.edit_profession(profile, profession_id, text, language), at=key)
        return [ProfileState.refresh_counts]

    @rx.event
    async def save(self, key: str, text: str) -> WriteEvents | None:
        """When leaving the field."""
        return await self._save(key, text)

    @rx.event
    async def save_from_form(self, data: dict[str, Any]) -> WriteEvents | None:
        """When pressing Enter."""
        return await self._save(str(data.get("key", "")), str(data.get("text", "")))

    @rx.event
    async def confirm(self, key: str) -> WriteEvents | None:
        """ "Still good" on a headline pending review, in either language."""
        row = self._row_of(key)
        if row is None or row["state"] != TextState.REVIEW:
            return None
        language = self.language
        await self._change(lambda profile: confirm_version(profile, language, key), at=key)
        return [ProfileState.refresh_counts]

    @rx.event
    async def same(self, key: str) -> WriteEvents | None:
        """ "Use the same text": the other version's text becomes this language's, saved right away."""
        row = self._row_of(key)
        if row is None or row["copyable"] != "yes":
            return None
        profession_id, language = row["id"], self.language
        await self._change(lambda profile: operations.copy_profession_text(profile, profession_id, language), at=key)
        return [ProfileState.refresh_counts]

    # -------------------------------------------------------------------- move

    @rx.event
    async def move(self, key: str, offset: int) -> WriteEvents | None:
        # The buttons only send one step; anything else did not come from them.
        row = self._row_of(key)
        if row is None or offset not in (-1, 1):
            return None
        profession_id = row["id"]
        moved = await self._change(lambda profile: operations.move_profession(profile, profession_id, offset), at=key)
        events: WriteEvents = [ProfileState.refresh_counts]
        if moved and (focus := focus_on(_focus_after_move(self.rows, key, offset))) is not None:
            events.append(focus)
        return events

    # ------------------------------------------------------------------ delete

    @rx.event
    def ask_delete(self, key: str) -> None:
        self._clear_error()
        # The only entry cannot be deleted: its button is disabled, and this is the same rule
        # for a request that did not come from it.
        if self._row_of(key) is not None and len(self.rows) > 1:
            self.confirming_key = key

    @rx.event
    def cancel_delete(self) -> rx.event.EventSpec | None:
        key = self.confirming_key
        self.confirming_key = ""
        self._clear_error()
        return focus_on(f"profession-delete-{key}")

    @rx.event
    async def confirm_delete(self, key: str) -> WriteEvents | None:
        """Only the headline whose question is open: the confirmation is required here and
        not only on screen, and a second click on Delete arrives once it is gone."""
        row = self._row_of(key)
        if row is None or key != self.confirming_key:
            return None
        target, profession_id = _focus_after_delete(self.rows, key), row["id"]
        deleted = await self._change(lambda profile: operations.remove_profession(profile, profession_id), at=key)
        if not deleted:
            return None
        self.confirming_key = ""
        events: WriteEvents = [ProfileState.refresh_counts]
        if (focus := focus_on(target)) is not None:
            events.append(focus)
        return events

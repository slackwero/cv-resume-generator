"""State of the list of professions in My profile → Contact.

Each entry is a complete headline with a version per language, edited in both. Every
change saves right away, the way the skills and achievements do, and not through
Contact's Save button.
"""

from typing import Any

import reflex as rx

from cv_generator.app.focus import focus_on
from cv_generator.app.states.profile_state import ProfileState, text_version
from cv_generator.app.states.text_list_state import TextListMixin, WriteEvents
from cv_generator.models.profile import MasterProfile
from cv_generator.services import professions as operations
from cv_generator.services.placeholders import is_usable_text
from cv_generator.services.translations import TextState, text_key

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


class ProfessionState(TextListMixin, rx.State):
    """Adds, edits, reorders and deletes the headlines of the master profile.

    Loading, following the language, saving and "Still good" come from `TextListMixin`.
    An error may also show in the add form (`ADD_FORM`).
    """

    rows: list[dict[str, str]] = []
    # The row whose delete question is open.
    confirming_key: str = ""

    async def _reload(self) -> None:
        """Opening the screen and switching the language draw the list again, with no delete
        question open."""
        self.confirming_key = ""
        await super()._reload()

    def _show(self, profile: MasterProfile | None) -> None:
        if profile is None:
            self.source_language = ""
            self.rows = []
            return
        self.source_language = profile.source_language or ""
        self.rows = profession_rows(profile, self.language)

    def _row_of(self, key: str) -> dict[str, str] | None:
        return next((row for row in self.rows if row["key"] == key), None)

    def _error_place(self, at: str) -> str:
        return at if at == ADD_FORM else super()._error_place(at)

    # --------------------------------------------------------------------- add

    @rx.event
    async def add(self, data: dict[str, Any]) -> WriteEvents | None:
        """Adds a headline at the end, written in the language on screen."""
        text, language = str(data.get("text", "")), self.language
        added = await self._change(lambda profile: operations.add_profession(profile, text, language), at=ADD_FORM)
        return [ProfileState.refresh_counts] if added else None

    # -------------------------------------------------------------------- edit

    async def _save(self, key: str, text: str) -> WriteEvents | None:
        row = self._row_of(key)
        if row is None or text.strip() == row["own"]:
            return None
        profession_id, language = row["id"], self.language
        await self._change(lambda profile: operations.edit_profession(profile, profession_id, text, language), at=key)
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

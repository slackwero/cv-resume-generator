"""What the lists of translatable texts in My profile share.

The professions in Contact and the texts LinkedIn feeds (presentation, education, courses
and languages) work the same way: they show in the language the rest of My profile shows,
and every change saves right away, starting from the profile on disk.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.app.errors import as_sentence, profile_not_read
from cv_generator.app.states.profile_state import ProfileState
from cv_generator.models.profile import MasterProfile
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import TextState
from cv_generator.services.translations import confirm as confirm_version

# What a write returns: the menu counts and the "What the CV needs" status read again from
# disk, since the write may have changed them.
WriteEvents = list[rx.event.EventSpec | rx.event.EventHandler]


class TextListMixin(rx.State, mixin=True):
    """Loads, shows and saves the rows of one list.

    Each state that mixes it in says how its rows are drawn from a profile (`_show`), found
    by key (`_row_of`) and saved (`_save`). A row is `profile_state.text_version` plus what
    the list adds.
    """

    # The language the rows are shown in, always the one the rest of My profile shows
    # (`ProfileState.language`); and the one LinkedIn feeds.
    language: str = ""
    source_language: str = ""
    error: str = ""
    # Where the error shows: a row key, or empty for the whole list.
    error_at: str = ""

    @rx.event
    async def start(self) -> None:
        """Loads the profile from disk, in the language the rest of My profile shows.

        It runs after `ProfileState.start` in the page's on_load and takes the language
        from it: after a switch that could not be remembered, the file holds the one before.
        """
        self.language = await self._screen_language()
        await self._reload()

    @rx.event
    async def show_language(self) -> None:
        """Follows the switch, which `ProfileState.switch_language` handles first in the same click."""
        language = await self._screen_language()
        if language == self.language:
            return
        self.language = language
        await self._reload()

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
        """ "Still good" on a text pending review, in either language."""
        row = self._row_of(key)
        if row is None or row["state"] != TextState.REVIEW:
            return None
        language = self.language
        await self._change(lambda profile: confirm_version(profile, language, key), at=key)
        return [ProfileState.refresh_counts]

    async def _screen_language(self) -> str:
        return (await self.get_state(ProfileState)).language

    async def _reload(self) -> None:
        """Shows the profile on disk. One that cannot be read shows as an error, not a crash."""
        self._clear_error()
        try:
            profile = await asyncio.to_thread(load_profile, DATA_DIR)
        except (ValueError, OSError) as error:
            self.error = profile_not_read(error)
            profile = None
        self._show(profile)

    def _clear_error(self) -> None:
        self.error = ""
        self.error_at = ""

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
            # cannot be read leaves the rows as they are.
            if on_disk is not None:
                self._show(on_disk)
            self.error_at = self._error_place(at)
            return False
        self._show(updated)
        return True

    def _error_place(self, at: str) -> str:
        """Where the error of an action on `at` shows: in its row, or above the list once the
        row is gone."""
        return at if self._row_of(at) is not None else ""

    # What each list says for itself.

    def _show(self, profile: MasterProfile | None) -> None:
        """Draws the rows from `profile`, or none when it could not be read."""
        raise NotImplementedError

    def _row_of(self, key: str) -> dict[str, str] | None:
        """The row on screen under this key, or None. The key comes from the browser, so it
        is looked up among the rows and never used to build anything."""
        raise NotImplementedError

    async def _save(self, key: str, text: str) -> WriteEvents | None:
        """The text of a row in the language on screen.

        It arrives twice per edit, on Enter and when leaving the field: if the text did not
        change, it does nothing.
        """
        raise NotImplementedError

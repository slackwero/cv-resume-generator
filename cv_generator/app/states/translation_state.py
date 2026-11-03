"""State of the Presentation, Education, Courses and Languages subsections of My profile.

LinkedIn feeds these texts, so in the source language they are read-only. In the other
language each one is translated by hand, and saves right away like the skills.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import reflex as rx

from cv_generator.app.config import DATA_DIR
from cv_generator.app.errors import as_sentence, readable
from cv_generator.app.states.profile_state import ProfileState, text_version
from cv_generator.models.profile import Course, Education, MasterProfile
from cv_generator.rendering.i18n import language_name
from cv_generator.services.profile import load_profile, save_profile
from cv_generator.services.translations import TextState, save_translation, source_text_of, text_key
from cv_generator.services.translations import confirm as confirm_version

# What a write returns: the menu counts read again from disk, since the write may have
# changed what is pending.
WriteEvents = list[rx.event.EventSpec | rx.event.EventHandler]

# The translatable fields of each subsection, with their label on screen.
SECTION_FIELDS: dict[str, dict[str, str]] = {
    "presentation": {"text": "Text"},
    "education": {"title": "Title"},
    "courses": {"name": "Name"},
    "languages": {"language": "Language", "level": "Level"},
}

# The profile list each subsection shows.
SECTION_LISTS: dict[str, str] = {
    "presentation": "profile_texts",
    "education": "education",
    "courses": "courses",
    "languages": "languages",
}


def _study_dates(study: Education) -> str:
    start = study.start or ""
    end = "present" if study.in_progress else study.end or ""
    return f"{start} — {end}".strip(" —") if start or end else ""


def _context(item: object) -> str:
    """The facts of an item that are not translated, to tell its rows apart."""
    if isinstance(item, Education):
        return " · ".join(part for part in (item.institution, _study_dates(item)) if part)
    if isinstance(item, Course):
        return " · ".join(part for part in (item.institution, str(item.year) if item.year else "") if part)
    return ""


def text_rows(profile: MasterProfile, language: str, section: str) -> list[dict[str, str]]:
    """The translatable texts of one subsection as rows, in profile order, in `language`.

    A row is editable in the other language only, and only when the source has text: in
    the source language LinkedIn writes it, and a translation of nothing would stay
    pending in a place nothing writes by hand.
    """
    in_source = language == profile.source_language
    rows: list[dict[str, str]] = []
    for item in getattr(profile, SECTION_LISTS[section]):
        for field, label in SECTION_FIELDS[section].items():
            key = text_key(item.id, field)
            rows.append(
                {
                    **text_version(profile, language, key),
                    "item_id": item.id,
                    "field": field,
                    "label": label,
                    "context": _context(item),
                    "editable": "yes" if not in_source and getattr(item, field) else "",
                }
            )
    return rows


def _all_rows(profile: MasterProfile, language: str) -> dict[str, list[dict[str, str]]]:
    return {section: text_rows(profile, language, section) for section in SECTION_FIELDS}


class TranslationState(rx.State):
    """Shows the texts LinkedIn feeds and translates them in the other language."""

    rows: dict[str, list[dict[str, str]]] = {section: [] for section in SECTION_FIELDS}
    language: str = ""
    source_language: str = ""
    error: str = ""
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

    async def _reload(self) -> None:
        """Shows the profile on disk. One that cannot be read shows as an error, not a crash."""
        self._clear_error()
        try:
            profile = await asyncio.to_thread(load_profile, DATA_DIR)
        except (ValueError, OSError) as error:
            self.error = f"Your profile could not be read: {readable(error)}"
            profile = None
        self._show(profile)

    async def _screen_language(self) -> str:
        return (await self.get_state(ProfileState)).language

    def _clear_error(self) -> None:
        self.error = ""
        self.error_at = ""

    def _show(self, profile: MasterProfile | None) -> None:
        if profile is None:
            self.source_language = ""
            self.rows = {section: [] for section in SECTION_FIELDS}
            return
        self.source_language = profile.source_language or ""
        self.rows = _all_rows(profile, self.language)

    def _row_of(self, key: str) -> dict[str, str] | None:
        """The row on screen under this key, or None. The key comes from the browser, so it
        is looked up among the rows and never used to build anything."""
        return next((row for rows in self.rows.values() for row in rows if row["key"] == key), None)

    async def _change(self, operation: Callable[[MasterProfile], MasterProfile], *, at: str) -> None:
        """Applies an operation and saves it right away.

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
            # Nothing was saved, but the screen may be the stale one. A profile that cannot
            # be read leaves the rows as they are.
            if on_disk is not None:
                self._show(on_disk)
            # An error of a row that is gone shows above the list.
            self.error_at = at if self._row_of(at) is not None else ""
            return
        self._show(updated)

    async def _save(self, key: str, text: str) -> WriteEvents | None:
        """The translation of a row. In the source language LinkedIn writes it: the row is
        not editable there.

        It arrives twice per edit, on Enter and when leaving the field: if the text did not
        change, it does nothing.
        """
        row = self._row_of(key)
        if row is None:
            return None
        if row["editable"] != "yes":
            self.error = f"The {language_name(self.source_language)} text comes from LinkedIn and is changed there."
            self.error_at = key
            return None
        if text.strip() == row["own"]:
            return None
        language = self.language
        await self._change(lambda profile: save_translation(profile, language, key, text), at=key)
        return [ProfileState.refresh_counts]

    @rx.event
    async def save_text(self, key: str, text: str) -> WriteEvents | None:
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

    @rx.event
    async def same_text(self, key: str) -> WriteEvents | None:
        """ "Use the same text": the source text becomes this language's, saved right away."""
        row = self._row_of(key)
        if row is None or row["copyable"] != "yes":
            return None
        language = self.language
        await self._change(
            lambda profile: save_translation(profile, language, key, source_text_of(profile, key)), at=key
        )
        return [ProfileState.refresh_counts]

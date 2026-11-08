"""State of the Presentation, Education, Courses and Languages subsections of My profile.

LinkedIn feeds these texts, so in the source language they are read-only. In the other
language each one is translated by hand, and saves right away like the skills.
"""

import reflex as rx

from cv_generator.app.states.profile_state import ProfileState, text_version
from cv_generator.app.states.text_list_state import TextListMixin, WriteEvents
from cv_generator.models.profile import Course, Education, MasterProfile
from cv_generator.rendering.i18n import language_name
from cv_generator.services.translations import save_translation, source_text_of, text_key

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


class TranslationState(TextListMixin, rx.State):
    """Shows the texts LinkedIn feeds and translates them in the other language.

    Loading, following the language, saving and "Still good" come from `TextListMixin`.
    """

    rows: dict[str, list[dict[str, str]]] = {section: [] for section in SECTION_FIELDS}

    def _show(self, profile: MasterProfile | None) -> None:
        if profile is None:
            self.source_language = ""
            self.rows = {section: [] for section in SECTION_FIELDS}
            return
        self.source_language = profile.source_language or ""
        self.rows = _all_rows(profile, self.language)

    def _row_of(self, key: str) -> dict[str, str] | None:
        return next((row for rows in self.rows.values() for row in rows if row["key"] == key), None)

    async def _save(self, key: str, text: str) -> WriteEvents | None:
        """The translation of a row. In the source language LinkedIn writes it: the row is
        not editable there."""
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
    async def same(self, key: str) -> WriteEvents | None:
        """ "Use the same text": the source text becomes this language's, saved right away."""
        row = self._row_of(key)
        if row is None or row["copyable"] != "yes":
            return None
        language = self.language
        await self._change(
            lambda profile: save_translation(profile, language, key, source_text_of(profile, key)), at=key
        )
        return [ProfileState.refresh_counts]

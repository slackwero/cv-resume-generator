"""The other language of the profile: states of a text, the rules that move them, and views.

The plain fields of an item hold the source-language text (the one LinkedIn feeds). The
other language lives in `MasterProfile.translations[language][key]`, where a key is
`"<item id>.<field>"`. Every function here is pure: it returns a new profile and never
mutates the one it receives.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cv_generator.models.profile import MasterProfile, Translation
from cv_generator.rendering.i18n import available_languages

PROFESSION_KEY = "personal.profession"

# The profile lists and the fields of their items that have a version per language.
# Achievements (their "text", nested in experiences) and the personal profession are handled besides.
FIELDS: dict[str, tuple[str, ...]] = {
    "professions": ("text",),
    "profile_texts": ("text",),
    "experiences": ("role", "location"),
    "education": ("title",),
    "courses": ("name",),
    "languages": ("language", "level"),
    "skills": ("name", "category", "level"),
    "hobbies": ("text",),
    "references": ("relationship",),
}

# Missing, these are not pending: a skill name is usually the same in both languages.
SILENT_FIELDS = frozenset({("skills", "name")})

# Which My profile section shows each list, for the pending counts.
SECTION_OF: dict[str, str] = {
    "profile_texts": "presentation",
    "experiences": "experience",
    "achievements": "experience",
    "education": "education",
    "courses": "courses",
    "languages": "languages",
    "skills": "skills",
    "professions": "contact",
    "personal": "contact",
}


class TextState(StrEnum):
    """Where one language version of a text stands against the other."""

    CURRENT = "current"
    MISSING = "missing"
    REVIEW = "review"


@dataclass(frozen=True)
class _Slot:
    """One translatable text of the profile: where it lives and what is stored there."""

    key: str
    list_name: str
    field: str
    item_id: str
    owner: Any
    source: str | None


def text_key(item_id: str, field: str) -> str:
    """The key of one field of one item in `MasterProfile.translations`."""
    return f"{item_id}.{field}"


def other_language(language: str) -> str:
    """The other of the two available languages."""
    others = [code for code in available_languages() if code != language]
    return others[0]


def _slots(profile: MasterProfile) -> Iterator[_Slot]:
    """Every translatable text of the items that exist, in profile order.

    Walking the real items, not the stored keys, is what makes keys of deleted items and
    unknown fields harmless.
    """
    yield _Slot(PROFESSION_KEY, "personal", "profession", "personal", profile.personal, profile.personal.profession)
    for list_name, fields in FIELDS.items():
        for item in getattr(profile, list_name):
            for field in fields:
                yield _Slot(text_key(item.id, field), list_name, field, item.id, item, getattr(item, field))
            if list_name == "experiences":
                for achievement in item.achievements:
                    yield _Slot(
                        text_key(achievement.id, "text"),
                        "achievements",
                        "text",
                        achievement.id,
                        achievement,
                        achievement.text,
                    )


def source_text_of(profile: MasterProfile, key: str) -> str:
    """The source-language text of a key; "" when it is empty, None or the item is gone."""
    for slot in _slots(profile):
        if slot.key == key:
            return slot.source or ""
    return ""


def states(source: str, entry: Translation | None) -> tuple[TextState, TextState]:
    """The states of (source version, other version) from the source text and the entry."""
    if not source and entry is None:
        return TextState.CURRENT, TextState.CURRENT
    if entry is None:
        return TextState.CURRENT, TextState.MISSING
    if not source:
        return TextState.MISSING, TextState.CURRENT
    if entry.source_text != source:
        return TextState.CURRENT, TextState.REVIEW
    if entry.agreed_text is not None and entry.agreed_text != entry.text:
        return TextState.REVIEW, TextState.CURRENT
    return TextState.CURRENT, TextState.CURRENT


def _translation_language(profile: MasterProfile, language: str) -> str:
    """The language whose `translations` hold the entry for a text viewed in `language`.

    A profile with no source language yet counts its plain fields as the source, so the
    viewed language is always the one that has translations.
    """
    return other_language(language) if language == profile.source_language else language


def _entry(profile: MasterProfile, language: str, key: str) -> Translation | None:
    return profile.translations.get(_translation_language(profile, language), {}).get(key)


def _state(profile: MasterProfile, language: str, key: str, source: str) -> TextState:
    source_state, other_state = states(source, _entry(profile, language, key))
    return source_state if language == profile.source_language else other_state


def state_in(profile: MasterProfile, language: str, key: str) -> TextState:
    """The state of the version of `key` in `language`."""
    return _state(profile, language, key, source_text_of(profile, key))


def text_in(profile: MasterProfile, language: str, key: str) -> str:
    """The text of `key` in `language`; when missing, the other version's text."""
    source = source_text_of(profile, key)
    entry = _entry(profile, language, key)
    if language == profile.source_language:
        return source or (entry.text if entry else "")
    return entry.text if entry else source


def _with_entries(profile: MasterProfile, language: str, entries: dict[str, Translation]) -> MasterProfile:
    """A copy of the profile where `language` holds exactly `entries` (dropped when empty)."""
    translations = {code: dict(items) for code, items in profile.translations.items()}
    if entries:
        translations[language] = entries
    else:
        translations.pop(language, None)
    return profile.model_copy(update={"translations": translations})


def save_translation(profile: MasterProfile, language: str, key: str, text: str) -> MasterProfile:
    """Saves the other-language text of `key` and moves the states by the review rules.

    Raises:
        ValueError: if `language` is the profile's source language: that text is not a
            translation, it lives in the item itself.
    """
    if language == profile.source_language:
        raise ValueError("The source language is not saved as a translation.")
    text = text.strip()
    entries = dict(profile.translations.get(language, {}))
    entry = entries.get(key)
    if not text:
        entries.pop(key, None)
        return _with_entries(profile, language, entries)
    source = source_text_of(profile, key)
    if entry is None:
        entries[key] = Translation(text=text, source_text=source)
    elif entry.text == text:
        return profile
    else:
        source_state, other_state = states(source, entry)
        if other_state is TextState.REVIEW:
            # Fixing the stale version: both agree again.
            entries[key] = Translation(text=text, source_text=source)
        elif source_state is TextState.REVIEW or not source:
            entries[key] = entry.model_copy(update={"text": text})
        else:
            entries[key] = entry.model_copy(update={"text": text, "agreed_text": entry.agreed_text or entry.text})
    return _with_entries(profile, language, entries)


def confirm(profile: MasterProfile, language: str, key: str) -> MasterProfile:
    """ "Still good" on either version: both are current again, no text changes.

    Raises:
        ValueError: if there is no translation or no source text to agree with.
    """
    translation_language = _translation_language(profile, language)
    entry = profile.translations.get(translation_language, {}).get(key)
    source = source_text_of(profile, key)
    if entry is None or not source:
        raise ValueError("There is nothing to confirm here.")
    entries = dict(profile.translations[translation_language])
    entries[key] = entry.model_copy(update={"source_text": source, "agreed_text": None})
    return _with_entries(profile, translation_language, entries)


def after_source_edit(profile: MasterProfile, key: str, previous: str) -> MasterProfile:
    """Applies the review rules after an editor changed a source text.

    Called by every editor of a source text, after the change, with the text it had
    before. If that text was in review or missing, the edit is a fix and every language
    agrees with the new text; otherwise the edit leaves the other versions to be reviewed.
    """
    source = source_text_of(profile, key)
    if source == previous:
        # An unchanged save is no fix: only "Still good" resolves a review.
        return profile
    translations = {code: dict(items) for code, items in profile.translations.items()}
    for items in translations.values():
        entry = items.get(key)
        if entry is not None and states(previous, entry)[0] in (TextState.REVIEW, TextState.MISSING):
            items[key] = entry.model_copy(update={"source_text": source, "agreed_text": None})
    return profile.model_copy(update={"translations": translations})


def copy_item(profile: MasterProfile, from_id: str, to_id: str) -> MasterProfile:
    """Copies every translation key of an item to another item, in every language."""
    prefix = f"{from_id}."
    translations = {code: dict(items) for code, items in profile.translations.items()}
    for items in translations.values():
        for key, entry in list(items.items()):
            if key.startswith(prefix):
                items[f"{to_id}.{key.removeprefix(prefix)}"] = entry
    return profile.model_copy(update={"translations": translations})


def drop_item(profile: MasterProfile, item_id: str) -> MasterProfile:
    """Removes every translation key of an item, in every language."""
    prefix = f"{item_id}."
    translations = {}
    for code, items in profile.translations.items():
        kept = {key: entry for key, entry in items.items() if not key.startswith(prefix)}
        if kept:
            translations[code] = kept
    return profile.model_copy(update={"translations": translations})


def in_language(profile: MasterProfile, language: str) -> MasterProfile:
    """A plain profile with every translatable text in `language`.

    Texts missing in `language` fall back to the other version. A field empty in both
    stays as it was (None stays None). The result has no translations and `language` as its
    source language, so it feeds the code that knows nothing of translations. A profile
    with no source language counts its plain fields as the source and applies the
    translations stored for `language`, if any.
    """
    view = profile.model_copy(deep=True)
    for slot in _slots(view):
        entry = _entry(profile, language, slot.key)
        if slot.source is None and entry is None:
            continue
        setattr(slot.owner, slot.field, text_in(profile, language, slot.key))
    view.translations = {}
    view.source_language = language
    return view


def field_states(profile: MasterProfile, language: str) -> dict[str, TextState]:
    """The keys that are pending in `language` (missing or in review), with their state."""
    return {slot.key: state for slot, state in _pending(profile, language)}


def _pending(profile: MasterProfile, language: str) -> Iterator[tuple[_Slot, TextState]]:
    for slot in _slots(profile):
        state = _state(profile, language, slot.key, slot.source or "")
        if state is TextState.CURRENT:
            continue
        if state is TextState.MISSING and (slot.list_name, slot.field) in SILENT_FIELDS:
            continue
        yield slot, state


def pending_totals(profile: MasterProfile, language: str) -> tuple[int, int]:
    """(missing, review) counts over the whole profile."""
    pending = [state for _, state in _pending(profile, language)]
    return pending.count(TextState.MISSING), pending.count(TextState.REVIEW)


def pending_by_section(profile: MasterProfile, language: str) -> dict[str, int]:
    """Pending texts per My profile section, with 0 for the sections that have none."""
    counts = dict.fromkeys(SECTION_OF.values(), 0)
    for slot, _ in _pending(profile, language):
        section = SECTION_OF.get(slot.list_name)
        if section is not None:
            counts[section] += 1
    return counts


def item_marks(profile: MasterProfile, language: str) -> dict[str, TextState]:
    """Item id -> MISSING when any of its fields is missing, else REVIEW. The profession is "personal"."""
    marks: dict[str, TextState] = {}
    for slot, state in _pending(profile, language):
        if marks.get(slot.item_id) is not TextState.MISSING:
            marks[slot.item_id] = state
    return marks

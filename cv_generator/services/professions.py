"""Add, edit, copy, reorder and remove the headlines that can go under the name.

Each entry is a complete headline with a version per language, like an achievement.
`personal.profession` stays as a mirror of the first usable entry so the code that still
reads it keeps working. Every operation returns a new profile, refreshes that mirror and
does not touch the one it receives.
"""

from cv_generator.models.profile import MasterProfile, Profession
from cv_generator.services.placeholders import PENDING_FIELD, is_usable_text
from cv_generator.services.translations import (
    TextState,
    after_source_edit,
    drop_item,
    other_language,
    save_translation,
    state_in,
    text_key,
)


def _own_text(profile: MasterProfile, profession: Profession) -> str | None:
    """The usable text an entry has: the source version, else the other language's."""
    if is_usable_text(profession.text):
        return profession.text
    entry = profile.translations.get(other_language(profile.source_language or ""), {}).get(
        text_key(profession.id, "text")
    )
    return entry.text if entry is not None and is_usable_text(entry.text) else None


def usable_professions(profile: MasterProfile) -> list[Profession]:
    """The entries with text in some language that is not the `PENDING` placeholder, in order."""
    return [profession for profession in profile.professions if _own_text(profile, profession) is not None]


def with_profession_mirror(profile: MasterProfile) -> MasterProfile:
    """Sets `personal.profession` to the first usable entry, in the source language if it has one."""
    usable = usable_professions(profile)
    mirror = (_own_text(profile, usable[0]) if usable else None) or PENDING_FIELD
    if profile.personal.profession == mirror:
        return profile
    return profile.model_copy(update={"personal": profile.personal.model_copy(update={"profession": mirror})})


def _valid_text(text: str) -> str:
    clean = text.strip()
    if not clean:
        raise ValueError("The profession cannot be empty.")
    return clean


def _index_of(profile: MasterProfile, profession_id: str) -> int:
    for index, profession in enumerate(profile.professions):
        if profession.id == profession_id:
            return index
    raise ValueError("That profession no longer exists in your profile. Reload the page.")


def _with_list(profile: MasterProfile) -> MasterProfile:
    """A deep copy whose list can be changed freely."""
    return profile.model_copy(deep=True)


def add_profession(profile: MasterProfile, text: str, language: str) -> MasterProfile:
    """Appends a headline written in `language`.

    In the other language the source text stays empty (pending) and the text is saved as
    that language's translation.

    Raises:
        ValueError: if the text is empty.
    """
    clean = _valid_text(text)
    result = _with_list(profile)
    if language == profile.source_language:
        result.professions.append(Profession(text=clean))
        return with_profession_mirror(result)
    created = Profession(text="")
    result.professions.append(created)
    return with_profession_mirror(save_translation(result, language, text_key(created.id, "text"), clean))


def edit_profession(profile: MasterProfile, profession_id: str, text: str, language: str) -> MasterProfile:
    """Changes the headline in `language`.

    In the other language it saves that language's translation and leaves the source text
    as it is. An empty text is refused there too: an entry added in that language has no
    source text, and would be left written in neither.

    Raises:
        ValueError: if the text is empty or the entry does not exist.
    """
    clean = _valid_text(text)
    index = _index_of(profile, profession_id)
    key = text_key(profession_id, "text")
    if language != profile.source_language:
        return with_profession_mirror(save_translation(profile, language, key, clean))

    result = _with_list(profile)
    previous = result.professions[index].text
    result.professions[index].text = clean
    return with_profession_mirror(after_source_edit(result, key, previous))


def copy_profession_text(profile: MasterProfile, profession_id: str, language: str) -> MasterProfile:
    """ "Use the same text": fills the version missing in `language` with the other one's text.

    Raises:
        ValueError: if the entry does not exist or its version in `language` is not missing.
    """
    _index_of(profile, profession_id)
    key = text_key(profession_id, "text")
    if state_in(profile, language, key) is not TextState.MISSING:
        raise ValueError("There is nothing to copy here: that version already has its text.")
    if language == profile.source_language:
        translated = profile.translations.get(other_language(language), {}).get(key)
        if translated is None:
            raise ValueError("There is nothing to copy here: the other version has no text.")
        return edit_profession(profile, profession_id, translated.text, language)
    source = next(p.text for p in profile.professions if p.id == profession_id)
    return edit_profession(profile, profession_id, source, language)


def move_profession(profile: MasterProfile, profession_id: str, offset: int) -> MasterProfile:
    """Moves a headline `offset` positions, stopping at the ends.

    Raises:
        ValueError: if the entry does not exist.
    """
    index = _index_of(profile, profession_id)
    result = _with_list(profile)
    target = max(0, min(len(result.professions) - 1, index + offset))
    result.professions.insert(target, result.professions.pop(index))
    return with_profession_mirror(result)


def remove_profession(profile: MasterProfile, profession_id: str) -> MasterProfile:
    """Removes a headline and its translations. The CV needs at least one.

    Already generated CVs do not change: they keep their own copy of the content.

    Raises:
        ValueError: if it is the last entry or does not exist.
    """
    index = _index_of(profile, profession_id)
    if len(profile.professions) == 1:
        raise ValueError("A CV needs a profession: keep at least one.")
    result = _with_list(profile)
    result.professions.pop(index)
    return with_profession_mirror(drop_item(result, profession_id))

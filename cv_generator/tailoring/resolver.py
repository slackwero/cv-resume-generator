"""Resolves a CV selection against the master profile.

This is where "I chose these achievements and not those" becomes the concrete content
of the document. The master profile is never modified.
"""

from typing import Protocol

from cv_generator.models.cv import CVContent, Selection
from cv_generator.models.profile import Experience, MasterProfile
from cv_generator.models.sections import Section


class ItemWithId(Protocol):
    """Any master profile item: all of them carry a stable id."""

    id: str


def _index[T: ItemWithId](items: list[T]) -> dict[str, T]:
    """Builds an index by id to resolve the selection references."""
    return {item.id: item for item in items}


def _take_in_order[T: ItemWithId](index: dict[str, T], ids: list[str], kind: str) -> list[T]:
    """Fetches the requested items, keeping the selection order.

    Raises:
        KeyError: if the selection references an id that no longer exists in the profile.
    """
    missing = [id_ for id_ in ids if id_ not in index]
    if missing:
        raise KeyError(f"{kind} not found in the master profile: {', '.join(missing)}")
    return [index[id_] for id_ in ids]


def _resolve_experiences(profile: MasterProfile, selection: Selection) -> list[Experience]:
    """Leaves each chosen experience with only the achievements marked for this CV."""
    experience_index = _index(profile.experiences)
    resolved_items: list[Experience] = []

    for chosen in selection.experiences:
        originals = _take_in_order(experience_index, [chosen.id], "experience")
        original = originals[0]
        achievements = _take_in_order(_index(original.achievements), chosen.achievements, "achievement")
        resolved_items.append(original.model_copy(deep=True, update={"achievements": achievements}))

    return resolved_items


def _resolve_sections(selection: Selection) -> list[Section]:
    """Drops the hidden sections and applies the chosen order."""
    visible_items = [section for section in selection.sections if section.visible]
    return sorted(visible_items, key=lambda section: section.order)


def resolve_content(profile: MasterProfile, selection: Selection) -> CVContent:
    """Builds the frozen content of a CV from the profile and the selection."""
    personal = profile.personal.model_copy(deep=True)
    if selection.header_profession:
        personal = personal.model_copy(update={"profession": selection.header_profession})
    if not selection.include_photo:
        personal = personal.model_copy(update={"photo": None})

    profile_text = None
    if selection.profile_text_id:
        chosen_items = _take_in_order(_index(profile.profile_texts), [selection.profile_text_id], "profile text")
        profile_text = chosen_items[0].text

    return CVContent(
        personal=personal,
        profile=profile_text,
        experiences=_resolve_experiences(profile, selection),
        education=_take_in_order(_index(profile.education), selection.education, "study"),
        courses=_take_in_order(_index(profile.courses), selection.courses, "course"),
        languages=_take_in_order(_index(profile.languages), selection.languages, "language"),
        skills=_take_in_order(_index(profile.skills), selection.skills, "skill"),
        hobbies=_take_in_order(_index(profile.hobbies), selection.hobbies, "hobby"),
        references=_take_in_order(_index(profile.references), selection.references, "reference"),
        sections=_resolve_sections(selection),
    )

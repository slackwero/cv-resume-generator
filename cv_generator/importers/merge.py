"""Merge of an imported draft into the master profile.

Syncing never overwrites or deletes. It produces a list of proposed changes the user
approves one by one; what they do not accept is left untouched.

The piece that makes the diff possible is `Achievement.imported_value`: it keeps the
text as it came from LinkedIn the last time. Comparing the current text, that origin
and what arrives now tells the four real cases apart:

    text == origin  and  incoming == origin   -> unchanged
    text == origin  and  incoming != origin   -> changed on LinkedIn, safe to apply
    text != origin  and  incoming == origin   -> you edited it, LinkedIn did not change
    text != origin  and  incoming != origin   -> conflict, the user decides

Achievements the owner added or duplicated (no `imported_value`) never take part, and
a LinkedIn one the owner deleted is not proposed again.
"""

import difflib
from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cv_generator.importers.base import ProfileDraft
from cv_generator.models.profile import (
    Achievement,
    Education,
    Experience,
    Language,
    MasterProfile,
    ProfileText,
    Skill,
)

# Below this similarity, an incoming text is considered a new item and not an edited
# version of the one that was already there.
SIMILARITY_THRESHOLD = 0.6

# A current job has no end date; for sorting it counts as the one that ends latest.
CURRENT_JOB_END = "9999-12"


class ChangeKind(StrEnum):
    """What the sync proposes for an item."""

    NEW = "new"
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    CONFLICT = "conflict"


class Change(BaseModel):
    """A proposed change, as it is shown to the user to decide."""

    key: str
    kind: ChangeKind
    section: str
    label: str
    current_text: str | None = None
    incoming_text: str | None = None

    payload: dict[str, Any] = Field(default_factory=dict)
    target_id: str | None = None
    experience_id: str | None = None


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _similarity(one: str, other_one: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(one), _normalize(other_one)).ratio()


def _experience_key(experience: Experience) -> tuple[str, str, str]:
    return (
        _normalize(experience.company),
        _normalize(experience.role),
        experience.start,
    )


def _reference(item: Achievement | ProfileText) -> str:
    """The text to compare against: the one that came from LinkedIn, if it is known."""
    return item.imported_value or item.text


def _match[T: Achievement | ProfileText](incoming: T, candidates: list[T]) -> T | None:
    """Looks for the previous version of the incoming item, tolerating minor edits."""
    if not candidates:
        return None

    best = max(candidates, key=lambda c: _similarity(_reference(incoming), _reference(c)))
    score = _similarity(_reference(incoming), _reference(best))
    return best if score >= SIMILARITY_THRESHOLD else None


def _classify(existing: Achievement | ProfileText, incoming: Achievement | ProfileText) -> ChangeKind:
    """Decides the kind of change by comparing current text, origin and incoming text."""
    origin = existing.imported_value
    edited_locally = origin is not None and _normalize(existing.text) != _normalize(origin)
    remote_change = _normalize(incoming.text) != _normalize(origin or existing.text)

    if not remote_change:
        return ChangeKind.UNCHANGED
    return ChangeKind.CONFLICT if edited_locally else ChangeKind.MODIFIED


def _diff_texts[T: Achievement | ProfileText](
    section: str,
    existing_items: list[T],
    incoming_items: list[T],
    experience_id: str | None = None,
    dismissed: Sequence[str] = (),
) -> list[Change]:
    """Compares two lists of free-text items (achievements or profile texts).

    `dismissed` are texts the owner deleted: an incoming item that matches none of the
    existing ones but is similar to one of those produces no change at all.
    """
    changes: list[Change] = []
    available = list(existing_items)

    for incoming in incoming_items:
        existing = _match(incoming, available)
        prefix = f"{section}:{experience_id}" if experience_id else section

        if existing is None:
            if any(_similarity(incoming.text, text) >= SIMILARITY_THRESHOLD for text in dismissed):
                continue
            changes.append(
                Change(
                    key=f"{prefix}:new:{incoming.id}",
                    kind=ChangeKind.NEW,
                    section=section,
                    label=incoming.text,
                    incoming_text=incoming.text,
                    payload=incoming.model_dump(),
                    experience_id=experience_id,
                )
            )
            continue

        available.remove(existing)
        changes.append(
            Change(
                key=f"{prefix}:{existing.id}",
                kind=_classify(existing, incoming),
                section=section,
                label=existing.text,
                current_text=existing.text,
                incoming_text=incoming.text,
                payload=incoming.model_dump(),
                target_id=existing.id,
                experience_id=experience_id,
            )
        )

    return changes


def _diff_by_name[T: BaseModel](
    section: str,
    existing_items: list[T],
    incoming_items: list[T],
    name: Callable[[T], str],
    already_known: frozenset[str] = frozenset(),
) -> list[Change]:
    """Compares lists whose text is a short name: skills, languages, studies.

    `already_known` are names that are not in the list but are not new either.
    """
    known = {_normalize(name(item)) for item in existing_items} | already_known
    changes: list[Change] = []

    for incoming in incoming_items:
        label = name(incoming)
        is_new = _normalize(label) not in known
        changes.append(
            Change(
                key=f"{section}:{_normalize(label)}",
                kind=ChangeKind.NEW if is_new else ChangeKind.UNCHANGED,
                section=section,
                label=label,
                incoming_text=label,
                payload=incoming.model_dump(),
            )
        )

    return changes


def _changed_data(existing: Experience, incoming: Experience) -> dict[str, Any]:
    """Dates and location that LinkedIn brings different for a job that was already there.

    A location that does not arrive does not erase the existing one: syncing never deletes.
    """
    changes: dict[str, Any] = {}
    if (incoming.end, incoming.current) != (existing.end, existing.current):
        changes |= {"end": incoming.end, "current": incoming.current}
    if incoming.location and incoming.location != existing.location:
        changes["location"] = incoming.location
    return changes


def _describe_job(experience: Experience) -> str:
    """The job as it is reviewed: without role and company it would not be clear which one it is."""
    parts = [experience.role, experience.company, experience.period(), experience.location]
    return " · ".join(part for part in parts if part)


def _known_skills(profile: MasterProfile) -> frozenset[str]:
    """A skill you renamed or removed here does not come back as new."""
    origins = [skill.imported_value for skill in profile.skills if skill.imported_value]
    return frozenset(_normalize(name) for name in [*origins, *profile.dismissed_skills])


def _diff_experiences(profile: MasterProfile, draft: ProfileDraft) -> list[Change]:
    """Matches positions by company, role and start date."""
    by_key = {_experience_key(e): e for e in profile.experiences}
    changes: list[Change] = []

    for incoming in draft.experiences:
        existing = by_key.get(_experience_key(incoming))
        label = f"{incoming.role} · {incoming.company}"

        if existing is None:
            changes.append(
                Change(
                    key=f"experiences:new:{incoming.id}",
                    kind=ChangeKind.NEW,
                    section="experiences",
                    label=label,
                    incoming_text=label,
                    payload=incoming.model_dump(),
                )
            )
            continue

        # Jobs are not edited by hand in the app, so a different value can only come from
        # LinkedIn: it is a safe change, never a conflict.
        data = _changed_data(existing, incoming)
        changes.append(
            Change(
                key=f"experiences:{existing.id}",
                kind=ChangeKind.MODIFIED if data else ChangeKind.UNCHANGED,
                section="experiences",
                label=label,
                current_text=_describe_job(existing) if data else label,
                incoming_text=_describe_job(existing.model_copy(update=data)) if data else label,
                payload=data,
                target_id=existing.id,
            )
        )
        # Only what came from LinkedIn takes part: a copy or an achievement of your own
        # would otherwise be matched, and proposed for change, as if LinkedIn had it.
        from_linkedin = [a for a in existing.achievements if a.imported_value is not None]
        changes += _diff_texts(
            "achievements",
            from_linkedin,
            incoming.achievements,
            existing.id,
            dismissed=existing.dismissed_achievements,
        )

    return changes


def compute_diff(profile: MasterProfile, draft: ProfileDraft) -> list[Change]:
    """Proposes the changes of a sync, without applying any."""
    return [
        *_diff_texts("profile_texts", profile.profile_texts, draft.profile_texts),
        *_diff_experiences(profile, draft),
        *_diff_by_name(
            "skills",
            profile.skills,
            draft.skills,
            lambda h: h.name,
            _known_skills(profile),
        ),
        *_diff_by_name("languages", profile.languages, draft.languages, lambda i: i.language),
        *_diff_by_name(
            "education",
            profile.education,
            draft.education,
            lambda e: f"{e.title} · {e.institution}",
        ),
        *_diff_by_name("courses", profile.courses, draft.courses, lambda c: c.name),
    ]


_BUILDERS: dict[str, type[BaseModel]] = {
    "profile_texts": ProfileText,
    "experiences": Experience,
    "skills": Skill,
    "languages": Language,
    "education": Education,
}


def _apply_one(profile: MasterProfile, change: Change) -> None:
    """Applies an already accepted change to the profile, in place."""
    if change.section == "achievements":
        _apply_achievement(profile, change)
        return
    if change.section == "experiences" and change.kind is not ChangeKind.NEW:
        _update_job(profile, change)
        return

    constructor = _BUILDERS.get(change.section)
    if constructor is None or change.kind is not ChangeKind.NEW:
        return

    getattr(profile, change.section).append(constructor.model_validate(change.payload))


def _update_job(profile: MasterProfile, change: Change) -> None:
    """Updates a job's dates and location, keeping its id and its achievements."""
    for index, experience in enumerate(profile.experiences):
        if experience.id == change.target_id:
            # Validated again: closing a job requires end and current to stay consistent.
            profile.experiences[index] = Experience.model_validate({**experience.model_dump(), **change.payload})
            return


def _apply_achievement(profile: MasterProfile, change: Change) -> None:
    """Adds or updates an achievement inside its experience, keeping the id."""
    experience = next((e for e in profile.experiences if e.id == change.experience_id), None)
    if experience is None:
        return

    if change.kind is ChangeKind.NEW:
        experience.achievements.append(Achievement.model_validate(change.payload))
        return

    achievement = next((item for item in experience.achievements if item.id == change.target_id), None)
    if achievement is not None and change.incoming_text:
        achievement.text = change.incoming_text
        achievement.imported_value = change.incoming_text


def _newest_first(experience: Experience) -> tuple[str, str]:
    return (experience.end or CURRENT_JOB_END, experience.start)


def apply_changes(profile: MasterProfile, changes: list[Change], accepted_items: set[str]) -> MasterProfile:
    """Returns a new profile with the accepted changes applied.

    The given profile is not modified, and nothing is removed: what is no longer on
    LinkedIn stays in the profile, because it may have been added by hand.

    Experiences are kept from newest to oldest. The CV prints them in the profile
    order, and a new experience goes in at the end of the list: without reordering, a
    freshly added current job came out last.
    """
    result = profile.model_copy(deep=True)

    for change in changes:
        if change.key in accepted_items and change.kind is not ChangeKind.UNCHANGED:
            _apply_one(result, change)

    result.experiences.sort(key=_newest_first, reverse=True)
    return result

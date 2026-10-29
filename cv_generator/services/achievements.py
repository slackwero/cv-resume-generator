"""Edit, duplicate, add, remove and reorder the achievements of a job by hand.

An achievement that came from LinkedIn keeps its `imported_value`, so the next sync can
tell "I edited it" apart from "it changed on LinkedIn". Every operation returns a new
profile and does not touch the one it receives, just like the skills.
"""

from enum import StrEnum

from cv_generator.models.profile import Achievement, Experience, MasterProfile
from cv_generator.text import normalize


class AchievementOrigin(StrEnum):
    """Where an achievement stands against LinkedIn, as the screen tags it."""

    LINKEDIN = "linkedin"
    EDITED = "edited"
    YOURS = "yours"


def origin_of(achievement: Achievement) -> AchievementOrigin:
    """Tells an untouched LinkedIn achievement from an edited one and from your own."""
    if achievement.imported_value is None:
        return AchievementOrigin.YOURS
    if achievement.text == achievement.imported_value:
        return AchievementOrigin.LINKEDIN
    return AchievementOrigin.EDITED


def _valid_text(text: str) -> str:
    clean = text.strip()
    if not clean:
        raise ValueError("The achievement cannot be empty.")
    return clean


def _experience_in(profile: MasterProfile, experience_id: str) -> Experience:
    for experience in profile.experiences:
        if experience.id == experience_id:
            return experience
    raise ValueError("That job no longer exists in your profile. Reload the page.")


def _index_of(experience: Experience, achievement_id: str) -> int:
    for index, achievement in enumerate(experience.achievements):
        if achievement.id == achievement_id:
            return index
    raise ValueError("That achievement no longer exists in your profile. Reload the page.")


def add_achievement(profile: MasterProfile, experience_id: str, text: str) -> MasterProfile:
    """Appends an achievement of your own at the end of the job.

    Raises:
        ValueError: if the text is empty or the job does not exist.
    """
    clean = _valid_text(text)
    _experience_in(profile, experience_id)

    result = profile.model_copy(deep=True)
    _experience_in(result, experience_id).achievements.append(Achievement(text=clean))
    return result


def edit_achievement(profile: MasterProfile, experience_id: str, achievement_id: str, text: str) -> MasterProfile:
    """Changes the text while keeping the id, the LinkedIn origin and the copy link.

    Raises:
        ValueError: if the text is empty or the job or achievement does not exist.
    """
    clean = _valid_text(text)
    index = _index_of(_experience_in(profile, experience_id), achievement_id)

    result = profile.model_copy(deep=True)
    _experience_in(result, experience_id).achievements[index].text = clean
    return result


def restore_linkedin_text(profile: MasterProfile, experience_id: str, achievement_id: str) -> MasterProfile:
    """Puts back the text LinkedIn gave for this achievement.

    Raises:
        ValueError: if it did not come from LinkedIn or the job or achievement does not exist.
    """
    experience = _experience_in(profile, experience_id)
    index = _index_of(experience, achievement_id)
    imported = experience.achievements[index].imported_value
    if imported is None:
        raise ValueError("This achievement did not come from LinkedIn.")

    result = profile.model_copy(deep=True)
    _experience_in(result, experience_id).achievements[index].text = imported
    return result


def duplicate_achievement(profile: MasterProfile, experience_id: str, achievement_id: str) -> MasterProfile:
    """Inserts a copy right below the original, so it can be reworded for another application.

    The copy is yours: it has no LinkedIn origin, and `copy_of` points to the original.

    Raises:
        ValueError: if the job or achievement does not exist.
    """
    index = _index_of(_experience_in(profile, experience_id), achievement_id)

    result = profile.model_copy(deep=True)
    achievements = _experience_in(result, experience_id).achievements
    original = achievements[index]
    achievements.insert(index + 1, Achievement(text=original.text, copy_of=original.id))
    return result


def remove_achievement(profile: MasterProfile, experience_id: str, achievement_id: str) -> MasterProfile:
    """Removes an achievement and, if it came from LinkedIn, remembers its LinkedIn text as dismissed.

    Its copies are not removed: they now point to what the removed one was a copy of, if anything.
    Already generated CVs do not change: they keep their own copy of the content.

    Raises:
        ValueError: if the job or achievement does not exist.
    """
    index = _index_of(_experience_in(profile, experience_id), achievement_id)

    result = profile.model_copy(deep=True)
    experience = _experience_in(result, experience_id)
    removed = experience.achievements.pop(index)
    if removed.imported_value is not None and all(
        normalize(dismissed) != normalize(removed.imported_value) for dismissed in experience.dismissed_achievements
    ):
        experience.dismissed_achievements.append(removed.imported_value)
    for achievement in experience.achievements:
        if achievement.copy_of == removed.id:
            achievement.copy_of = removed.copy_of
    return result


def move_achievement(profile: MasterProfile, experience_id: str, achievement_id: str, offset: int) -> MasterProfile:
    """Moves an achievement `offset` positions inside its job, stopping at the ends.

    Raises:
        ValueError: if the job or achievement does not exist.
    """
    index = _index_of(_experience_in(profile, experience_id), achievement_id)

    result = profile.model_copy(deep=True)
    achievements = _experience_in(result, experience_id).achievements
    target = max(0, min(len(achievements) - 1, index + offset))
    achievements.insert(target, achievements.pop(index))
    return result

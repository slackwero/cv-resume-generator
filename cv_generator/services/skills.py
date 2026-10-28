"""Create, rename and remove skills by hand in the master profile.

The LinkedIn PDF only carries the three "top skills", so the rest is filled in here.
Every operation returns a new profile and does not touch the one it receives, just
like the sync.
"""

from cv_generator.models.profile import MasterProfile, Skill
from cv_generator.text import normalize


def _valid_name(name: str) -> str:
    clean = name.strip()
    if not clean:
        raise ValueError("The skill name cannot be empty.")
    return clean


def _require_absent(profile: MasterProfile, name: str, except_id: str | None = None) -> None:
    """Two skills that only differ in case or accents are the same one."""
    for skill in profile.skills:
        if skill.id != except_id and normalize(skill.name) == normalize(name):
            raise ValueError(f"You already have the skill '{skill.name}'.")


def _index_of(profile: MasterProfile, skill_id: str) -> int:
    for index, skill in enumerate(profile.skills):
        if skill.id == skill_id:
            return index
    raise ValueError(f"The skill {skill_id!r} does not exist in the profile.")


def add_skill(profile: MasterProfile, name: str) -> MasterProfile:
    """Appends a skill at the end of the profile.

    If you had removed it before, it is no longer dismissed: creating it again is the
    sign that you want it back.

    Raises:
        ValueError: if the name is empty or that skill already exists.
    """
    clean = _valid_name(name)
    _require_absent(profile, clean)

    result = profile.model_copy(deep=True)
    result.skills.append(Skill(name=clean))
    result.dismissed_skills = [
        dismissed for dismissed in result.dismissed_skills if normalize(dismissed) != normalize(clean)
    ]
    return result


def rename_skill(profile: MasterProfile, skill_id: str, name: str) -> MasterProfile:
    """Changes a skill's name while keeping its id.

    The name it came with from LinkedIn stays as the origin, and if it had none (skills
    imported before the field existed) the previous name is used.

    Raises:
        ValueError: if the name is empty, belongs to another skill, or the id does not exist.
    """
    clean = _valid_name(name)
    index = _index_of(profile, skill_id)
    _require_absent(profile, clean, except_id=skill_id)

    result = profile.model_copy(deep=True)
    skill = result.skills[index]
    skill.imported_value = skill.imported_value or skill.name
    skill.name = clean
    return result


def remove_skill(profile: MasterProfile, skill_id: str) -> MasterProfile:
    """Removes a skill and remembers it as dismissed.

    Already generated CVs do not change: they keep their own copy of the content.

    Raises:
        ValueError: if the id does not exist.
    """
    index = _index_of(profile, skill_id)

    result = profile.model_copy(deep=True)
    removed = result.skills.pop(index)
    remembered = removed.imported_value or removed.name
    if all(normalize(dismissed) != normalize(remembered) for dismissed in result.dismissed_skills):
        result.dismissed_skills.append(remembered)
    return result

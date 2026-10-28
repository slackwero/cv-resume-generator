"""Create, rename and remove skills by hand in the master profile.

LinkedIn only delivers the three "top skills" in the PDF, so the user needs to complete
the rest here. What they do by hand has to survive the next sync: that is tested in
test_merge.py.
"""

import pytest

from cv_generator.models.profile import MasterProfile, Skill
from cv_generator.services.skills import add_skill, remove_skill, rename_skill
from tests.test_models_personal import REQUIRED


@pytest.fixture
def profile() -> MasterProfile:
    return MasterProfile(
        personal=REQUIRED,
        skills=[
            Skill(id="skill-pipelines", name="Pipelines", imported_value="Pipelines"),
            Skill(id="skill-python", name="Python"),
        ],
    )


def _names(profile: MasterProfile) -> list[str]:
    return [skill.name for skill in profile.skills]


# ------------------------------------------------------------------ add


def test_add_appends_the_skill_at_the_end(profile: MasterProfile) -> None:
    result = add_skill(profile, "  Kubernetes  ")

    assert _names(result) == ["Pipelines", "Python", "Kubernetes"]
    assert result.skills[-1].imported_value is None, "a skill created by hand did not come from LinkedIn"


def test_add_does_not_modify_the_given_profile(profile: MasterProfile) -> None:
    add_skill(profile, "Kubernetes")

    assert _names(profile) == ["Pipelines", "Python"]


@pytest.mark.parametrize("name", ["", "   "])
def test_add_rejects_an_empty_name(profile: MasterProfile, name: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        add_skill(profile, name)


@pytest.mark.parametrize("name", ["python", "PYTHON", " Python "])
def test_add_rejects_an_existing_one_even_with_different_case(profile: MasterProfile, name: str) -> None:
    with pytest.raises(ValueError, match="You already have"):
        add_skill(profile, name)


def test_adding_a_dismissed_one_removes_it_from_dismissed(profile: MasterProfile) -> None:
    """If you create it again it is because you want it: the sync no longer has to keep it quiet."""
    profile.dismissed_skills = ["Terraform"]

    result = add_skill(profile, "terraform")

    assert result.dismissed_skills == []


# ---------------------------------------------------------------- rename


def test_rename_changes_the_name_and_keeps_the_id(profile: MasterProfile) -> None:
    result = rename_skill(profile, "skill-python", "Python 3")

    assert _names(result) == ["Pipelines", "Python 3"]
    assert result.skills[1].id == "skill-python", "CVs already generated point to this id"


def test_rename_keeps_the_name_it_came_with_from_linkedin(profile: MasterProfile) -> None:
    """Without the origin, the next sync would bring 'Pipelines' as new."""
    result = rename_skill(profile, "skill-pipelines", "CI/CD Pipelines")
    result = rename_skill(result, "skill-pipelines", "GitLab CI/CD Pipelines")

    assert result.skills[0].imported_value == "Pipelines"


def test_renaming_one_without_origin_keeps_the_old_name_as_origin(profile: MasterProfile) -> None:
    """Skills imported before the origin existed do not have it, but their name did come from LinkedIn."""
    result = rename_skill(profile, "skill-python", "Python 3")

    assert result.skills[1].imported_value == "Python"


def test_rename_allows_fixing_only_the_case(profile: MasterProfile) -> None:
    result = rename_skill(profile, "skill-python", "PYTHON")

    assert _names(result) == ["Pipelines", "PYTHON"]


def test_rename_rejects_another_skill_name(profile: MasterProfile) -> None:
    with pytest.raises(ValueError, match="You already have"):
        rename_skill(profile, "skill-python", "pipelines")


def test_rename_rejects_an_empty_name(profile: MasterProfile) -> None:
    with pytest.raises(ValueError, match="empty"):
        rename_skill(profile, "skill-python", "  ")


def test_renaming_a_missing_one_fails(profile: MasterProfile) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        rename_skill(profile, "skill-missing", "Go")


# ----------------------------------------------------------------- remove


def test_remove_takes_it_out_of_the_profile(profile: MasterProfile) -> None:
    result = remove_skill(profile, "skill-python")

    assert _names(result) == ["Pipelines"]


def test_remove_remembers_the_name_it_came_with_from_linkedin(profile: MasterProfile) -> None:
    """That way the next sync does not propose it to you again."""
    renamed = rename_skill(profile, "skill-pipelines", "CI/CD Pipelines")

    result = remove_skill(renamed, "skill-pipelines")

    assert result.dismissed_skills == ["Pipelines"]


def test_removing_one_without_origin_remembers_its_name(profile: MasterProfile) -> None:
    result = remove_skill(profile, "skill-python")

    assert result.dismissed_skills == ["Python"]


def test_remove_does_not_repeat_a_dismissed_one(profile: MasterProfile) -> None:
    profile.dismissed_skills = ["python"]

    assert remove_skill(profile, "skill-python").dismissed_skills == ["python"]


def test_removing_a_missing_one_fails(profile: MasterProfile) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        remove_skill(profile, "skill-missing")

import pytest

from cv_generator.models.cv import SelectedExperience, Selection
from cv_generator.models.profile import Achievement, Experience, MasterProfile, ProfileText, Skill
from cv_generator.models.sections import Section, SectionKind
from cv_generator.tailoring.resolver import resolve_content
from tests.test_models_personal import REQUIRED
from tests.test_photo import sample_photo


@pytest.fixture
def profile() -> MasterProfile:
    return MasterProfile(
        personal=REQUIRED,
        profile_texts=[
            ProfileText(id="profile-generic", text="Cloud-focused engineer."),
            ProfileText(id="profile-security", text="Application security specialist."),
        ],
        experiences=[
            Experience(
                id="exp-acme",
                company="Acme Airlines",
                role="DevSecOps Engineer",
                start="2022-03",
                current=True,
                achievements=[
                    Achievement(id="achievement-sast", text="Cut critical SAST findings by 80%."),
                    Achievement(id="achievement-costs", text="Halved the BigQuery cost."),
                    Achievement(id="achievement-k8s", text="Migrated 40 services to Kubernetes."),
                ],
            ),
            Experience(
                id="exp-previous",
                company="Previous Consulting",
                role="Backend Developer",
                start="2019-01",
                end="2022-02",
                achievements=[Achievement(id="achievement-api", text="Built the payments API.")],
            ),
        ],
        skills=[
            Skill(id="skill-python", name="Python"),
            Skill(id="skill-k8s", name="Kubernetes"),
            Skill(id="skill-sast", name="SAST"),
        ],
    )


@pytest.fixture
def devsecops_selection() -> Selection:
    return Selection(
        profile_text_id="profile-security",
        header_profession="DevSecOps Engineer",
        experiences=[SelectedExperience(id="exp-acme", achievements=["achievement-sast", "achievement-k8s"])],
        skills=["skill-sast", "skill-python"],
        sections=[
            Section(kind=SectionKind.PROFILE, title="About me", order=1),
            Section(kind=SectionKind.EXPERIENCE, title="Career", order=2),
            Section(kind=SectionKind.HOBBIES, title="Hobbies", order=3, visible=False),
        ],
    )


def test_includes_only_the_marked_achievements(profile: MasterProfile, devsecops_selection: Selection) -> None:
    content = resolve_content(profile, devsecops_selection)

    texts = [achievement.text for achievement in content.experiences[0].achievements]
    assert texts == [
        "Cut critical SAST findings by 80%.",
        "Migrated 40 services to Kubernetes.",
    ]


def test_omits_unselected_experiences(profile: MasterProfile, devsecops_selection: Selection) -> None:
    content = resolve_content(profile, devsecops_selection)

    assert [experience.id for experience in content.experiences] == ["exp-acme"]


def test_respects_the_selection_skill_order(profile: MasterProfile, devsecops_selection: Selection) -> None:
    content = resolve_content(profile, devsecops_selection)

    assert [skill.name for skill in content.skills] == ["SAST", "Python"]


def test_uses_the_chosen_profile_text(profile: MasterProfile, devsecops_selection: Selection) -> None:
    content = resolve_content(profile, devsecops_selection)

    assert content.profile == "Application security specialist."


def test_the_header_profession_overrides_the_master_profile_one(
    profile: MasterProfile, devsecops_selection: Selection
) -> None:
    content = resolve_content(profile, devsecops_selection)

    assert profile.personal.profession == "DevSecOps Engineer"
    assert content.personal.profession == "DevSecOps Engineer"


def test_keeps_the_profile_profession_if_the_selection_does_not_override_it(
    profile: MasterProfile, devsecops_selection: Selection
) -> None:
    devsecops_selection.header_profession = "Cloud Security Architect"

    content = resolve_content(profile, devsecops_selection)

    assert content.personal.profession == "Cloud Security Architect"
    assert profile.personal.profession == "DevSecOps Engineer", "the master profile must not mutate"


def test_gives_only_visible_sections_in_order(profile: MasterProfile, devsecops_selection: Selection) -> None:
    content = resolve_content(profile, devsecops_selection)

    assert [(s.kind, s.title) for s in content.sections] == [
        (SectionKind.PROFILE, "About me"),
        (SectionKind.EXPERIENCE, "Career"),
    ]


def test_fails_if_the_selection_points_to_a_missing_achievement(profile: MasterProfile) -> None:
    selection = Selection(
        experiences=[SelectedExperience(id="exp-acme", achievements=["achievement-ghost"])],
    )

    with pytest.raises(KeyError, match="achievement-ghost"):
        resolve_content(profile, selection)


def test_includes_the_profile_photo_if_the_selection_asks(
    profile: MasterProfile, devsecops_selection: Selection
) -> None:
    profile.personal.photo = sample_photo()

    content = resolve_content(profile, devsecops_selection)

    assert content.personal.photo == profile.personal.photo


def test_leaves_the_photo_out_if_the_selection_excludes_it(
    profile: MasterProfile, devsecops_selection: Selection
) -> None:
    """Some applications expect a CV without a photo, even if the profile has one."""
    profile.personal.photo = sample_photo()
    devsecops_selection.include_photo = False

    content = resolve_content(profile, devsecops_selection)

    assert content.personal.photo is None
    assert profile.personal.photo is not None, "the master profile is never modified"


def test_a_recipe_from_before_the_photo_option_includes_it() -> None:
    """CVs generated before the option existed do not carry it in their recipe."""
    assert Selection.model_validate({}).include_photo is True

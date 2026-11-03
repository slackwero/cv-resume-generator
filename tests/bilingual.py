"""A small bilingual profile shared by the tests of the translation features."""

from cv_generator.models.profile import (
    Achievement,
    Education,
    Experience,
    MasterProfile,
    PersonalInfo,
    Profession,
    Skill,
)


def sample_profile() -> MasterProfile:
    """An English-source profile with no Spanish yet: one job, one achievement, one skill."""
    return MasterProfile(
        source_language="en",
        personal=PersonalInfo(
            first_name="Ana",
            last_name="Rojas",
            profession="DevSecOps Engineer",
            phone="+56 9 1111 2222",
            email="ana@example.com",
        ),
        # What a loaded profile always has: the upgrade writes the headline as the first entry.
        professions=[Profession(id="profession-headline", text="DevSecOps Engineer")],
        experiences=[
            Experience(
                id="exp-1",
                company="Acme Airlines",
                role="Platform Engineer",
                location="Santiago, Chile",
                start="2022-03",
                achievements=[Achievement(id="ach-1", text="Cut deploy time by 40%")],
            )
        ],
        skills=[Skill(id="skill-1", name="Kubernetes")],
        education=[Education(id="edu-1", institution="Universidad de Chile", title="BSc Computer Science")],
    )

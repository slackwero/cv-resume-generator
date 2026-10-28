"""The first sync, when no profile exists yet.

This path was cut off: it compared against an empty profile and then aborted right
away, so a new user could not create their profile by any route.
"""

from pathlib import Path

from cv_generator.importers.base import PartialPersonalInfo, ProfileDraft
from cv_generator.importers.merge import Achievement, ChangeKind, Experience, Skill, compute_diff
from cv_generator.services.profile import PENDING_FIELD, load_profile, pending_fields
from cv_generator.services.sync import (
    apply_sync,
    create_initial_profile,
    empty_profile,
    preselection,
)


def _draft() -> ProfileDraft:
    return ProfileDraft(
        personal=PartialPersonalInfo(
            first_name="Jane",
            last_name="Doe",
            profession="DevSecOps Engineer",
            email="jane.doe@example.com",
        ),
        experiences=[
            Experience(
                company="Acme Airlines",
                role="DevSecOps Engineer",
                start="2022-03",
                achievements=[Achievement(text="Automated vulnerability scanning")],
            )
        ],
        skills=[Skill(name="Go"), Skill(name="Terraform")],
    )


def test_marks_as_pending_the_phone_linkedin_does_not_provide() -> None:
    profile = create_initial_profile(_draft().personal)

    assert profile.personal.phone == PENDING_FIELD


def test_keeps_what_the_importer_did_bring() -> None:
    profile = create_initial_profile(_draft().personal)

    assert profile.personal.first_name == "Jane"
    assert profile.personal.email == "jane.doe@example.com"


def test_pending_fields_names_only_what_is_missing() -> None:
    profile = create_initial_profile(_draft().personal)

    assert pending_fields(profile) == ["phone"]


def test_a_complete_profile_leaves_no_pending_fields() -> None:
    full = PartialPersonalInfo(
        first_name="Jane",
        last_name="Doe",
        profession="DevSecOps Engineer",
        phone="+1 555 0100",
        email="jane.doe@example.com",
    )

    assert pending_fields(create_initial_profile(full)) == []


def test_without_profile_everything_imported_is_proposed_as_new() -> None:
    changes = compute_diff(empty_profile(), _draft())

    assert changes
    assert {change.kind for change in changes} == {ChangeKind.NEW}


def test_without_profile_everything_comes_premarked() -> None:
    """Nothing to review the first time: there is no text of your own that could be lost."""
    changes = compute_diff(empty_profile(), _draft())

    assert preselection(changes) == {change.key for change in changes}


def test_the_first_sync_leaves_a_profile_that_reads_back(tmp_path: Path) -> None:
    """The underlying regression: a profile built without validation does not survive the disk."""
    draft = _draft()
    changes = compute_diff(empty_profile(), draft)

    apply_sync(
        profile=create_initial_profile(draft.personal),
        changes=changes,
        accepted_items=preselection(changes),
        data_dir=tmp_path,
        source="linkedin_zip",
        detected_language="es",
    )

    recovered = load_profile(tmp_path)
    assert recovered is not None
    assert [e.role for e in recovered.experiences] == ["DevSecOps Engineer"]
    assert sorted(h.name for h in recovered.skills) == ["Go", "Terraform"]


def test_achievements_come_with_their_experience_on_the_first_sync(tmp_path: Path) -> None:
    draft = _draft()
    changes = compute_diff(empty_profile(), draft)

    apply_sync(
        profile=create_initial_profile(draft.personal),
        changes=changes,
        accepted_items=preselection(changes),
        data_dir=tmp_path,
        source="linkedin_zip",
        detected_language="es",
    )

    recovered = load_profile(tmp_path)
    assert recovered is not None
    assert [achievement.text for achievement in recovered.experiences[0].achievements] == [
        "Automated vulnerability scanning"
    ]

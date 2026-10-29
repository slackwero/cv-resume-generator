import pytest

from cv_generator.importers.base import PartialPersonalInfo, ProfileDraft
from cv_generator.importers.merge import Change, ChangeKind, apply_changes, compute_diff
from cv_generator.models.profile import Achievement, Experience, MasterProfile, Skill
from cv_generator.services.achievements import (
    add_achievement,
    duplicate_achievement,
    edit_achievement,
    remove_achievement,
)
from cv_generator.services.skills import remove_skill, rename_skill
from tests.test_models_personal import REQUIRED


def _draft(achievement_text: str = "Cut SAST findings by 80%.") -> ProfileDraft:
    return ProfileDraft(
        personal=PartialPersonalInfo(first_name="Jane", last_name="Doe"),
        experiences=[
            Experience(
                company="Northwind",
                role="Platform Engineer",
                start="2020-04",
                current=True,
                achievements=[Achievement(text=achievement_text, imported_value=achievement_text)],
            )
        ],
        skills=[Skill(name="Kubernetes")],
    )


def _draft_with(*achievement_texts: str) -> ProfileDraft:
    """The same job, with these LinkedIn achievements in this order."""
    draft = _draft()
    draft.experiences[0].achievements = [Achievement(text=text, imported_value=text) for text in achievement_texts]
    return draft


@pytest.fixture
def empty_profile() -> MasterProfile:
    return MasterProfile(personal=REQUIRED)


def _sync(profile: MasterProfile, draft: ProfileDraft) -> MasterProfile:
    """Accepts every proposed change, as the user would in the interface."""
    changes = compute_diff(profile, draft)
    return apply_changes(profile, changes, {change.key for change in changes})


def test_against_an_empty_profile_everything_is_new(empty_profile: MasterProfile) -> None:
    changes = compute_diff(empty_profile, _draft())

    assert all(change.kind is ChangeKind.NEW for change in changes)
    assert any(change.section == "experiences" for change in changes)


def test_the_first_sync_populates_the_profile(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())

    assert [e.company for e in profile.experiences] == ["Northwind"]
    assert [h.name for h in profile.skills] == ["Kubernetes"]


def test_resyncing_the_same_proposes_no_change(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())

    changes = compute_diff(profile, _draft())

    assert [c for c in changes if c.kind is not ChangeKind.UNCHANGED] == []


def test_resync_duplicates_nothing(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile = _sync(profile, _draft())

    assert len(profile.experiences) == 1
    assert len(profile.experiences[0].achievements) == 1
    assert len(profile.skills) == 1


def test_resync_keeps_ids_so_generated_cvs_do_not_break(
    empty_profile: MasterProfile,
) -> None:
    profile = _sync(empty_profile, _draft())
    experience_id = profile.experiences[0].id
    achievement_id = profile.experiences[0].achievements[0].id

    profile = _sync(profile, _draft())

    assert profile.experiences[0].id == experience_id
    assert profile.experiences[0].achievements[0].id == achievement_id


def test_an_achievement_i_edited_by_hand_survives_the_sync(
    empty_profile: MasterProfile,
) -> None:
    profile = _sync(empty_profile, _draft())
    profile.experiences[0].achievements[0].text = "Cut critical SAST findings by 80% in six months."

    profile = _sync(profile, _draft())

    assert profile.experiences[0].achievements[0].text == ("Cut critical SAST findings by 80% in six months.")
    assert len(profile.experiences[0].achievements) == 1, "the LinkedIn version must not reappear"


def test_a_linkedin_change_on_an_untouched_achievement_is_proposed_as_modified(
    empty_profile: MasterProfile,
) -> None:
    profile = _sync(empty_profile, _draft())

    changes = compute_diff(profile, _draft("Cut SAST findings by 90%."))

    modified = [c for c in changes if c.kind is ChangeKind.MODIFIED]
    assert len(modified) == 1
    assert modified[0].incoming_text == "Cut SAST findings by 90%."


def test_editing_here_and_there_at_once_is_a_conflict(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile.experiences[0].achievements[0].text = "My own wording of the achievement."

    changes = compute_diff(profile, _draft("Cut SAST findings by 90%."))

    conflicts = [c for c in changes if c.kind is ChangeKind.CONFLICT]
    assert len(conflicts) == 1
    assert conflicts[0].current_text == "My own wording of the achievement."
    assert conflicts[0].incoming_text == "Cut SAST findings by 90%."


def test_a_conflict_i_do_not_accept_leaves_my_version_intact(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile.experiences[0].achievements[0].text = "My own wording of the achievement."

    changes = compute_diff(profile, _draft("Cut SAST findings by 90%."))
    profile = apply_changes(profile, changes, accepted_items=set())

    assert profile.experiences[0].achievements[0].text == "My own wording of the achievement."


def test_a_conflict_i_accept_takes_the_linkedin_version(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile.experiences[0].achievements[0].text = "My own wording of the achievement."

    changes = compute_diff(profile, _draft("Cut SAST findings by 90%."))
    conflict = next(c for c in changes if c.kind is ChangeKind.CONFLICT)
    profile = apply_changes(profile, changes, accepted_items={conflict.key})

    assert profile.experiences[0].achievements[0].text == "Cut SAST findings by 90%."


def test_what_i_delete_on_linkedin_is_not_deleted_from_my_profile(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile.skills.append(Skill(name="Skill I added by hand"))

    draft_without_skills = _draft()
    draft_without_skills.skills = []
    profile = _sync(profile, draft_without_skills)

    first_name = [h.name for h in profile.skills]
    assert "Kubernetes" in first_name, "syncing never deletes: it only adds and updates"
    assert "Skill I added by hand" in first_name


def test_sync_does_not_mutate_the_given_profile(empty_profile: MasterProfile) -> None:
    _sync(empty_profile, _draft())

    assert empty_profile.experiences == []


def test_a_new_experience_is_placed_by_date_not_at_the_end(empty_profile: MasterProfile) -> None:
    """It happened with the real PDF: the current job, freshly added on LinkedIn, came out last in the CV."""
    contoso = Experience(company="Contoso", role="SRE Lead", start="2018-10", end="2020-03")
    profile = _sync(empty_profile, ProfileDraft(experiences=[contoso]))
    profile = _sync(profile, _draft())

    draft = _draft()
    draft.experiences = [
        Experience(company="Fabrikam", role="Security Architect", start="2024-09", current=True),
        *draft.experiences,
        contoso,
        Experience(company="Tailspin", role="Software Engineer", start="2016-05", end="2017-02"),
    ]
    profile = _sync(profile, draft)

    assert [e.company for e in profile.experiences] == ["Fabrikam", "Northwind", "Contoso", "Tailspin"]


def _job_change(profile: MasterProfile, draft: ProfileDraft) -> Change:
    return next(c for c in compute_diff(profile, draft) if c.section == "experiences")


def test_a_job_you_closed_on_linkedin_is_proposed_closed_here(empty_profile: MasterProfile) -> None:
    """It happened with the real PDF: the Northwind job ended in May 2025 and the profile kept it current."""
    profile = _sync(empty_profile, _draft())
    northwind = profile.experiences[0]

    draft = _draft()
    draft.experiences[0] = draft.experiences[0].model_copy(update={"end": "2024-08", "current": False})
    change = _job_change(profile, draft)
    profile = apply_changes(profile, [change], {change.key})

    assert change.kind is ChangeKind.MODIFIED
    assert "2020-04 — present" in change.current_text
    assert "2020-04 — 2024-08" in change.incoming_text
    closed = profile.experiences[0]
    assert (closed.end, closed.current) == ("2024-08", False)
    assert closed.id == northwind.id, "CVs already generated point to this id"
    assert closed.achievements == northwind.achievements


def test_a_new_linkedin_location_is_proposed(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())

    draft = _draft()
    draft.experiences[0].location = "Madrid, Spain"
    change = _job_change(profile, draft)

    assert change.kind is ChangeKind.MODIFIED
    assert apply_changes(profile, [change], {change.key}).experiences[0].location == "Madrid, Spain"


def test_a_missing_location_does_not_erase_the_existing_one(empty_profile: MasterProfile) -> None:
    """The PDF does not always bring the location, and syncing never deletes."""
    draft = _draft()
    draft.experiences[0].location = "Madrid, Spain"
    profile = _sync(empty_profile, draft)

    assert _job_change(profile, _draft()).kind is ChangeKind.UNCHANGED


def _skill_kinds(profile: MasterProfile, draft: ProfileDraft) -> dict[str, ChangeKind]:
    return {c.label: c.kind for c in compute_diff(profile, draft) if c.section == "skills"}


def test_a_skill_you_renamed_does_not_come_back_as_new(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile = rename_skill(profile, profile.skills[0].id, "Kubernetes (GKE y EKS)")

    assert _skill_kinds(profile, _draft()) == {"Kubernetes": ChangeKind.UNCHANGED}


def test_a_skill_you_removed_does_not_come_back(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile = remove_skill(profile, profile.skills[0].id)

    assert _skill_kinds(profile, _draft()) == {"Kubernetes": ChangeKind.UNCHANGED}
    assert _sync(profile, _draft()).skills == []


def test_a_new_linkedin_skill_keeps_being_proposed(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    profile = remove_skill(profile, profile.skills[0].id)

    draft = _draft()
    draft.skills.append(Skill(name="Terraform", imported_value="Terraform"))

    assert _skill_kinds(profile, draft) == {
        "Kubernetes": ChangeKind.UNCHANGED,
        "Terraform": ChangeKind.NEW,
    }


def _achievement_changes(changes: list[Change]) -> list[Change]:
    return [c for c in changes if c.section == "achievements"]


def test_a_copy_is_never_matched_against_linkedin(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    job = profile.experiences[0]
    original = job.achievements[0]
    profile = duplicate_achievement(profile, job.id, original.id)

    assert [c for c in compute_diff(profile, _draft()) if c.kind is not ChangeKind.UNCHANGED] == []
    # Worded exactly as LinkedIn has it now: by text alone, the copy would be the closest match.
    copy = profile.experiences[0].achievements[1]
    profile = edit_achievement(profile, job.id, copy.id, "Cut SAST findings by 85%.")
    changed = _achievement_changes(compute_diff(profile, _draft("Cut SAST findings by 85%.")))
    assert [c.target_id for c in changed] == [original.id]


def test_deleting_the_original_and_keeping_the_copy_brings_nothing_back(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    job = profile.experiences[0]
    original = job.achievements[0]
    profile = duplicate_achievement(profile, job.id, original.id)
    profile = remove_achievement(profile, job.id, original.id)
    copy = profile.experiences[0].achievements[0]

    assert _achievement_changes(compute_diff(profile, _draft())) == []
    after = _sync(profile, _draft())
    assert [(a.id, a.text, a.imported_value) for a in after.experiences[0].achievements] == [
        (copy.id, "Cut SAST findings by 80%.", None)
    ]


def test_a_deleted_linkedin_achievement_is_not_proposed_again(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    job = profile.experiences[0]
    profile = remove_achievement(profile, job.id, job.achievements[0].id)

    assert _achievement_changes(compute_diff(profile, _draft())) == []


def test_one_linkedin_rewrote_beyond_recognition_comes_back_as_new(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft())
    job = profile.experiences[0]
    profile = remove_achievement(profile, job.id, job.achievements[0].id)

    changed = _achievement_changes(compute_diff(profile, _draft("Led the migration of 40 services to Kubernetes.")))

    assert [c.kind for c in changed] == [ChangeKind.NEW]


SAST = "Cut SAST findings by 80%."
DAST = "Cut DAST findings by 80%."


def test_a_deleted_achievement_does_not_take_over_a_similar_one(empty_profile: MasterProfile) -> None:
    """With the deleted one first on LinkedIn, it matched the similar one left and replaced its text."""
    profile = _sync(empty_profile, _draft_with(SAST, DAST))
    job = profile.experiences[0]
    sast, dast = job.achievements
    profile = remove_achievement(profile, job.id, sast.id)

    changed = _achievement_changes(compute_diff(profile, _draft_with(SAST, DAST)))
    assert [c for c in changed if c.kind is not ChangeKind.UNCHANGED] == []
    after = _sync(profile, _draft_with(SAST, DAST))
    assert [(a.id, a.text) for a in after.experiences[0].achievements] == [(dast.id, DAST)]


def test_a_slightly_changed_deleted_achievement_stays_deleted(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft(SAST))
    job = profile.experiences[0]
    profile = remove_achievement(profile, job.id, job.achievements[0].id)

    assert _achievement_changes(compute_diff(profile, _draft("Cut SAST findings by 85%."))) == []


def test_of_two_identical_bullets_the_kept_one_still_matches(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft_with(SAST, SAST))
    job = profile.experiences[0]
    deleted, kept = job.achievements
    profile = remove_achievement(profile, job.id, deleted.id)

    for draft in (_draft_with(SAST), _draft_with(SAST, SAST)):
        changed = _achievement_changes(compute_diff(profile, draft))
        assert [(c.kind, c.target_id) for c in changed] == [(ChangeKind.UNCHANGED, kept.id)]


def test_an_achievement_of_yours_is_never_proposed_for_change(empty_profile: MasterProfile) -> None:
    profile = _sync(empty_profile, _draft("Rotated every pipeline secret."))
    job = profile.experiences[0]
    profile = add_achievement(profile, job.id, "Cut SAST findings by 80%.")
    yours = profile.experiences[0].achievements[-1]

    changed = _achievement_changes(compute_diff(profile, _draft("Cut SAST findings by 80%.")))
    assert yours.id not in {c.target_id for c in changed}
    assert ChangeKind.NEW in {c.kind for c in changed}

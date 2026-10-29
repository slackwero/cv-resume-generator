"""A new CV starts copies unchecked, and "Refresh list" brings in what you changed in My profile.

A copy says nearly what its original says: with both checked the CV would repeat itself.
Refreshing must keep every check you made and never leave a mark on an achievement that
no longer exists, or the selection would name a missing id.
"""

from cv_generator.app.states.wizard_state import (
    initial_achievement_marks,
    refreshed_achievement_marks,
    with_refreshed_achievements,
)
from cv_generator.models.profile import Achievement, Experience, MasterProfile
from tests.test_models_personal import REQUIRED

SCAN = "Automated scanning in 120 pipelines."
TRIAGE = "Built a FastAPI triage service."
PIPES = "Rebuilt the deployment pipelines."


def _key(experience_id: str, achievement_id: str) -> str:
    return f"{experience_id}|{achievement_id}"


def _linkedin(achievement_id: str, text: str) -> Achievement:
    return Achievement(id=achievement_id, text=text, imported_value=text)


def _acme(*achievements: Achievement) -> Experience:
    return Experience(
        id="exp-acme",
        company="Acme Cloud",
        role="DevSecOps Engineer",
        start="2022-03",
        current=True,
        achievements=list(achievements),
    )


def _north() -> Experience:
    return Experience(
        id="exp-north",
        company="Northwind",
        role="Platform Engineer",
        start="2019-01",
        end="2022-02",
        achievements=[_linkedin("pipes", PIPES)],
    )


def _profile(*experiences: Experience) -> MasterProfile:
    return MasterProfile(personal=REQUIRED, experiences=list(experiences))


# ------------------------------------------------------------------ a new CV


def test_a_copy_starts_unchecked_and_everything_else_checked() -> None:
    profile = _profile(
        _acme(
            _linkedin("scan", SCAN),
            Achievement(id="copy-1", text=SCAN, copy_of="scan"),
            _linkedin("triage", TRIAGE),
        ),
        _north(),
    )

    assert initial_achievement_marks(profile) == {
        _key("exp-acme", "scan"): True,
        _key("exp-acme", "copy-1"): False,
        _key("exp-acme", "triage"): True,
        _key("exp-north", "pipes"): True,
    }


def test_a_chain_of_copies_leaves_only_the_original_checked() -> None:
    profile = _profile(
        _acme(
            _linkedin("scan", SCAN),
            Achievement(id="copy-1", text=SCAN, copy_of="scan"),
            Achievement(id="copy-2", text=SCAN, copy_of="copy-1"),
        )
    )

    assert initial_achievement_marks(profile) == {
        _key("exp-acme", "scan"): True,
        _key("exp-acme", "copy-1"): False,
        _key("exp-acme", "copy-2"): False,
    }


def test_a_copy_whose_original_is_gone_starts_checked() -> None:
    profile = _profile(_acme(Achievement(id="copy-1", text=SCAN, copy_of="deleted-id")))

    assert initial_achievement_marks(profile) == {_key("exp-acme", "copy-1"): True}


# ------------------------------------------------------------------ refresh


def test_refresh_keeps_your_checks_and_checks_new_ones() -> None:
    marks = {
        _key("exp-acme", "scan"): False,
        _key("exp-acme", "triage"): True,
        _key("exp-north", "pipes"): False,
    }
    previous = _profile(_acme(_linkedin("scan", SCAN), _linkedin("triage", TRIAGE)), _north())
    refreshed = _profile(
        _acme(
            _linkedin("scan", SCAN),
            _linkedin("triage", TRIAGE),
            Achievement(id="rag", text="Designed a RAG pipeline over runbooks."),
        ),
        _north(),
    )

    assert refreshed_achievement_marks(marks, previous, refreshed) == {
        _key("exp-acme", "scan"): False,
        _key("exp-acme", "triage"): True,
        _key("exp-acme", "rag"): True,
        _key("exp-north", "pipes"): False,
    }


def test_refresh_drops_deleted_achievements() -> None:
    marks = {
        _key("exp-acme", "scan"): True,
        _key("exp-acme", "triage"): True,
        _key("exp-north", "pipes"): True,
    }
    previous = _profile(_acme(_linkedin("scan", SCAN), _linkedin("triage", TRIAGE)), _north())
    refreshed = _profile(_acme(_linkedin("scan", SCAN)), _north())

    result = refreshed_achievement_marks(marks, previous, refreshed)

    assert _key("exp-acme", "triage") not in result
    assert result == {_key("exp-acme", "scan"): True, _key("exp-north", "pipes"): True}


def test_refresh_checks_a_new_copy_and_unchecks_its_original() -> None:
    marks = {_key("exp-acme", "scan"): True}
    previous = _profile(_acme(_linkedin("scan", SCAN)))
    refreshed = _profile(_acme(_linkedin("scan", SCAN), Achievement(id="copy-1", text=SCAN, copy_of="scan")))

    assert refreshed_achievement_marks(marks, previous, refreshed) == {
        _key("exp-acme", "scan"): False,
        _key("exp-acme", "copy-1"): True,
    }


def test_refresh_does_not_check_an_original_you_had_unchecked() -> None:
    marks = {_key("exp-acme", "scan"): False}
    previous = _profile(_acme(_linkedin("scan", SCAN)))
    refreshed = _profile(_acme(_linkedin("scan", SCAN), Achievement(id="copy-1", text=SCAN, copy_of="scan")))

    assert refreshed_achievement_marks(marks, previous, refreshed) == {
        _key("exp-acme", "scan"): False,
        _key("exp-acme", "copy-1"): True,
    }


def test_a_copy_placed_above_its_original_still_unchecks_it() -> None:
    marks = {_key("exp-acme", "scan"): True}
    previous = _profile(_acme(_linkedin("scan", SCAN)))
    refreshed = _profile(_acme(Achievement(id="copy-1", text=SCAN, copy_of="scan"), _linkedin("scan", SCAN)))

    assert refreshed_achievement_marks(marks, previous, refreshed) == {
        _key("exp-acme", "copy-1"): True,
        _key("exp-acme", "scan"): False,
    }


def test_refresh_gives_a_deleted_originals_check_to_its_copy() -> None:
    """You deleted the original to keep the copy you adapted: it takes the original's place in this CV."""
    marks = {_key("exp-acme", "scan"): True, _key("exp-acme", "copy-1"): False}
    previous = _profile(_acme(_linkedin("scan", SCAN), Achievement(id="copy-1", text=SCAN, copy_of="scan")))
    refreshed = _profile(_acme(Achievement(id="copy-1", text=SCAN, copy_of=None)))

    assert refreshed_achievement_marks(marks, previous, refreshed) == {_key("exp-acme", "copy-1"): True}


def test_refresh_does_not_check_a_copy_whose_unchecked_original_was_deleted() -> None:
    marks = {_key("exp-acme", "scan"): False, _key("exp-acme", "copy-1"): False}
    previous = _profile(_acme(_linkedin("scan", SCAN), Achievement(id="copy-1", text=SCAN, copy_of="scan")))
    refreshed = _profile(_acme(Achievement(id="copy-1", text=SCAN, copy_of=None)))

    assert refreshed_achievement_marks(marks, previous, refreshed) == {_key("exp-acme", "copy-1"): False}


def test_refreshed_profile_updates_this_cvs_jobs_only() -> None:
    current = _profile(_acme(_linkedin("scan", SCAN), _linkedin("triage", TRIAGE)), _north())
    before = current.model_dump()
    on_disk = _profile(
        _acme(
            Achievement(id="triage", text="Built a FastAPI triage service for 40 teams.", imported_value=TRIAGE),
            Achievement(id="scan", text="Automated scanning in 140 pipelines.", imported_value=SCAN),
        ),
        Experience(id="exp-new", company="Initech", role="SRE", start="2025-01", current=True),
    )

    result = with_refreshed_achievements(current, on_disk)

    assert [experience.id for experience in result.experiences] == ["exp-acme", "exp-north"]
    assert result.experiences[0].achievements == on_disk.experiences[0].achievements
    assert result.experiences[1] == current.experiences[1]
    assert result.personal == current.personal
    assert current.model_dump() == before

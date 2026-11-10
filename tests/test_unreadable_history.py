"""A history.json that is not a list of CVs: Home says so and rebuilds it from the CVs.

The list is an index over data/cvs, where every CV keeps its own copy, so the app can
rebuild it. A damaged one used to stop Home's own event with a traceback.
"""

from datetime import datetime
from pathlib import Path

import pytest

from cv_generator.app.states import wizard_state
from cv_generator.app.states.home_state import HomeState
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.models.cv import CVContent, GeneratedCV, Selection
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services.generation import save_cv
from cv_generator.services.profile import save_profile
from cv_generator.storage.history import UnreadableHistoryError, register_cv
from tests.bilingual import sample_profile
from tests.screens import new_state, run
from tests.test_models_personal import REQUIRED

DAMAGED = b'{"entries": [ '
UNREADABLE = "Your list of CVs could not be read: history.json is not valid JSON"


def _saved_cv(data_dir: Path, name: str = "Northwind") -> GeneratedCV:
    cv = GeneratedCV(
        created=datetime(2026, 10, 27, 9, 0),  # noqa: DTZ001
        cv_name=name,
        target_role="DevSecOps Engineer",
        language="en",
        template="sidebar",
        pdf_file=str(data_dir / "northwind.pdf"),
        selection=Selection(),
        content=CVContent(personal=REQUIRED),
    )
    save_cv(data_dir, cv)
    register_cv(data_dir, cv)
    return cv


def test_home_opens_and_offers_to_rebuild_the_list(screen_data: Path) -> None:
    save_profile(screen_data, sample_profile())
    _saved_cv(screen_data)
    (screen_data / "history.json").write_bytes(DAMAGED)
    home = new_state(HomeState)

    run(HomeState.load, home)

    assert home.history_error.startswith(UNREADABLE)
    assert home.history == []
    # The profile is fine, and says so.
    assert home.has_profile
    assert home.profile_error == ""
    assert (screen_data / "history.json").read_bytes() == DAMAGED


def test_rebuilding_brings_the_cvs_back_and_keeps_the_damaged_file(screen_data: Path) -> None:
    _saved_cv(screen_data, "Northwind")
    (screen_data / "history.json").write_bytes(DAMAGED)
    home = new_state(HomeState)
    run(HomeState.load, home)

    run(HomeState.rebuild_list, home)

    assert home.history_error == ""
    assert [row["name"] for row in home.history] == ["Northwind"]
    aside = list(screen_data.glob("history.*.json"))
    assert len(aside) == 1
    assert aside[0].read_bytes() == DAMAGED
    assert aside[0].name in home.notice


def test_a_list_that_breaks_while_home_is_open_is_said_on_archive(screen_data: Path) -> None:
    cv = _saved_cv(screen_data)
    home = new_state(HomeState)
    run(HomeState.load, home)
    (screen_data / "history.json").write_bytes(DAMAGED)

    run(HomeState.archive, home, cv.cv_id, True)
    assert home.message.startswith("That CV could not be archived: history.json is not valid JSON")

    run(HomeState.note_reason, home, cv.cv_id, "Closed")
    assert home.message.startswith("The reason could not be saved: history.json is not valid JSON")
    assert (screen_data / "history.json").read_bytes() == DAMAGED


def test_the_wizard_says_the_list_is_damaged_instead_of_blaming_the_selection(
    screen_data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def damaged(**_: object) -> None:
        raise UnreadableHistoryError("history.json is not valid JSON (line 1, column 15)")

    monkeypatch.setattr(wizard_state, "generate_cv", damaged)
    wizard = new_state(WizardState)
    wizard._profile = MasterProfile(personal=PersonalInfo(**REQUIRED))  # noqa: SLF001

    run(WizardState.generate, wizard)

    assert wizard.action_error.startswith(UNREADABLE)
    assert "selection" not in wizard.action_error
    assert not wizard.generating

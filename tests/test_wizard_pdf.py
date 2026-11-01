"""What the wizard says when the PDF cannot be written or opened."""

import errno
from pathlib import Path

import pytest

from cv_generator.app.states import wizard_state
from cv_generator.app.states.wizard_state import WizardState
from cv_generator.models.profile import MasterProfile, PersonalInfo
from cv_generator.services.system import ViewerUnavailable
from tests.screens import new_state, run
from tests.test_models_personal import REQUIRED


@pytest.fixture
def wizard(screen_data: Path) -> WizardState:
    state = new_state(WizardState)
    state._profile = MasterProfile(personal=PersonalInfo(**REQUIRED))
    return state


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(errno.EACCES, "Permission denied", "/home/x/output/cv.pdf"),
        OSError(errno.ENOSPC, "No space left on device"),
    ],
)
def test_a_pdf_that_cannot_be_written_gets_the_folder_advice_and_no_viewer_hint(
    wizard: WizardState, monkeypatch: pytest.MonkeyPatch, error: OSError
) -> None:
    def fail(**_: object) -> None:
        raise error

    monkeypatch.setattr(wizard_state, "generate_cv", fail)

    run(WizardState.generate, wizard)

    assert wizard.action_error.startswith("The PDF could not be written to output/: ")
    assert wizard.action_error.endswith("Check that the folder exists and is writable.")
    assert "viewer" not in wizard.action_error
    assert not wizard.generating


def _open_failing_with(error: Exception, wizard: WizardState, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(path: Path, allowed_dir: Path) -> None:
        raise error

    wizard.generated_cv = "output/cv.pdf"
    monkeypatch.setattr(wizard_state, "open_with_viewer", fail)
    run(WizardState.open_the_pdf, wizard)


def _unavailable(cause: OSError) -> ViewerUnavailable:
    try:
        raise cause
    except OSError as caught:
        unavailable = ViewerUnavailable("no viewer")
        unavailable.__cause__ = caught
    return unavailable


def test_a_viewer_that_cannot_start_is_said_not_raised(wizard: WizardState, monkeypatch: pytest.MonkeyPatch) -> None:
    cause = PermissionError(errno.EACCES, "Permission denied", "/x/viewer")

    _open_failing_with(_unavailable(cause), wizard, monkeypatch)

    assert wizard.action_error.startswith("Your PDF viewer could not be opened: ")
    assert "Open cv.pdf from the output/ folder yourself." in wizard.action_error


def test_a_missing_viewer_program_is_not_reported_as_a_system_error(
    wizard: WizardState, monkeypatch: pytest.MonkeyPatch
) -> None:
    cause = FileNotFoundError(errno.ENOENT, "No such file or directory", "xdg-open")

    _open_failing_with(_unavailable(cause), wizard, monkeypatch)

    assert "no program to open PDFs was found" in wizard.action_error
    assert "the system said" not in wizard.action_error

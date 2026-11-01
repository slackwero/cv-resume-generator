"""How an error reads on screen.

The services raise ValueError with a sentence written for the screen; those go as they
are. The system's OSError reads like "[Errno 13] Permission denied:
'/Users/…/data/.profile.json.tmp'", which says nothing the owner can act on.
"""

import errno
import os

import pytest

from cv_generator.app.errors import as_sentence, pdf_not_written, readable


def test_a_message_written_for_the_screen_goes_as_it_is() -> None:
    assert readable(ValueError("The achievement cannot be empty.")) == "The achievement cannot be empty."


def test_an_oserror_built_with_a_message_of_ours_goes_as_it_is() -> None:
    assert readable(FileNotFoundError("the backup 'profile-1.json' does not exist")) == (
        "the backup 'profile-1.json' does not exist"
    )


@pytest.mark.parametrize("code", [errno.EACCES, errno.EPERM])
def test_a_permission_error_names_the_folder_and_not_the_path(code: int) -> None:
    error = OSError(code, "Permission denied", "/Users/someone/cv-generator/data/.profile.json.tmp")

    assert readable(error) == "this computer did not let the app use its data folder"


def test_a_permission_error_without_a_file_names_no_folder() -> None:
    error = OSError(errno.EACCES, "Permission denied")

    assert readable(error) == "this computer did not let the app use a file it needs"


@pytest.mark.parametrize(
    ("code", "text"),
    [
        (errno.ENOSPC, "the disk is full"),
        (errno.EROFS, "the disk does not accept changes"),
        (errno.EIO, "the system said: input/output error"),
    ],
)
def test_other_disk_errors_read_plainly(code: int, text: str) -> None:
    assert readable(OSError(code, os.strerror(code), "/Users/someone/cv-generator/data/profile.json")) == text


def test_a_disk_error_on_its_own_is_a_sentence() -> None:
    """For the notices that show only the error, with no "could not be saved:" before it."""
    assert as_sentence(OSError(errno.ENOSPC, "No space left on device")) == "Nothing was saved: the disk is full."
    assert as_sentence(ValueError("The achievement cannot be empty.")) == "The achievement cannot be empty."


def test_a_pdf_that_is_locked_tells_the_owner_to_close_the_viewer() -> None:
    error = PermissionError(errno.EACCES, "Permission denied", "/Users/someone/cv-generator/output/cv.pdf")

    assert pdf_not_written(error).endswith("If the PDF is open in a viewer, close it and try again.")
    assert "output" in pdf_not_written(error)


def test_other_errors_writing_a_pdf_get_no_viewer_hint() -> None:
    error = OSError(errno.ENOSPC, "No space left on device", "/Users/someone/cv-generator/output/cv.pdf")

    assert pdf_not_written(error) == "the disk is full"

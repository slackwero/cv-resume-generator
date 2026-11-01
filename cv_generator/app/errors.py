"""How an error reads on screen.

The services raise ValueError with a sentence written for the screen. The system raises
OSError, whose text is for a programmer: "[Errno 13] Permission denied:
'/Users/…/data/.profile.json.tmp'". Here it becomes what happened, in words the owner
can act on.
"""

import errno
from pathlib import Path

_PERMISSION = {errno.EACCES, errno.EPERM}


def readable(error: BaseException) -> str:
    """The error as a phrase that can follow "could not be saved: ".

    A system error says what happened and, for a permission, which of the app's folders,
    never the full path. An OSError raised with a message of our own (no `errno`) goes as
    it is, like any other error.
    """
    if not isinstance(error, OSError) or error.errno is None:
        return str(error)
    if error.errno in _PERMISSION:
        folder = Path(error.filename).parent.name if error.filename else ""
        where = f"its {folder} folder" if folder else "a file it needs"
        return f"this computer did not let the app use {where}"
    if error.errno == errno.ENOSPC:
        return "the disk is full"
    if error.errno == errno.EROFS:
        return "the disk does not accept changes"
    said = (error.strerror or "an unknown error").lower()
    return f"the system said: {said}"


def as_sentence(error: BaseException) -> str:
    """The error on its own, for the notices that show nothing else.

    A system error gets the sentence around it; a message written for the screen already
    is one.
    """
    if isinstance(error, OSError) and error.errno is not None:
        return f"Nothing was saved: {readable(error)}."
    return str(error)

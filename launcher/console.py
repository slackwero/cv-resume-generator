"""What the launcher says, asks and records.

The person reading the console double-clicked a file and is not a developer, so the
messages are plain and short. Everything technical (commands, installer output, errors)
goes to `start.log` instead, which is what they can send to whoever helps them.
"""

import contextlib
import os
import subprocess
import sys
import traceback
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

LOG_NAME = "start.log"

_YES = {"", "y", "yes"}
_NO = {"n", "no"}


def say(message: str) -> None:
    """Prints a message right away, even when the output is a pipe."""
    print(message, flush=True)


def ask(question: str, *, assume_yes: bool, read: Callable[[str], str] = input) -> bool:
    """Asks a yes/no question; Enter means yes.

    With no terminal to answer on (closed input) the answer is no: nothing gets
    installed because nobody was there to agree to it.
    """
    if assume_yes:
        return True
    while True:
        try:
            answer = read(f"{question} [Y/n] ").strip().lower()
        except EOFError:
            return False
        if answer in _YES:
            return True
        if answer in _NO:
            return False
        say("Please answer y or n.")


def open_log(folder: Path) -> TextIO:
    """Starts a fresh `start.log` in `folder`, so it only holds the latest run."""
    log = (folder / LOG_NAME).open("w", encoding="utf-8")
    log.write(f"{datetime.now().isoformat(timespec='seconds')} {sys.platform} Python {sys.version.split()[0]}\n")
    log.flush()
    return log


def log_exception(folder: Path) -> None:
    """Adds the traceback of the exception being handled to `start.log`, if the folder allows it.

    It appends: by the time an error reaches the launcher's last line of defence, the run's
    log is already closed, or was never opened because the error came first.
    """
    with contextlib.suppress(OSError), (folder / LOG_NAME).open("a", encoding="utf-8") as log:
        traceback.print_exc(file=log)


def run_logged(
    command: Sequence[str],
    log: TextIO,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    heartbeat_seconds: float = 60,
) -> bool:
    """Runs a command with its output in the log; True when it exits with 0.

    stdin is closed on purpose: password prompts from `sudo` read the terminal
    directly, so they still work. The heartbeat tells the person a slow installer has
    not frozen, since its output is not on the screen.
    """
    log.write(f"$ {' '.join(command)}\n")
    log.flush()
    try:
        process = subprocess.Popen(  # noqa: S603 - the commands are constants of the launcher
            list(command),
            cwd=cwd,
            env={**os.environ, **(env or {})},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    except OSError as error:
        log.write(f"Could not start {command[0]}: {error}\n")
        log.flush()
        return False

    minutes = 0
    waited = 0.0
    while True:
        try:
            process.wait(timeout=heartbeat_seconds)
            break
        except subprocess.TimeoutExpired:
            waited += heartbeat_seconds
            minutes = int(waited // 60)
            say(f"Still working ({minutes} min)...")
    log.write(f"[exit code {process.returncode}]\n")
    log.flush()
    return process.returncode == 0

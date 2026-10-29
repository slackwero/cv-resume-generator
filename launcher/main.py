"""The launcher's flow: from checking the port to a running app in the browser.

Every step either carries on or ends with one plain sentence and an exit code, so the
person who double-clicked a file never has to read a traceback; that goes to `start.log`.
The other modules are called through their module (`app.port_state`, ...) so the tests can
replace them and never start an app, install anything or open a browser.
"""

import argparse
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import NoReturn, TextIO

from launcher import app, console, prerequisites

PROJECT_FOLDER = Path(__file__).resolve().parent.parent

# Set once the launcher is on its way out; from then on a stop signal does nothing.
_stopping = False


class _Failure(Exception):
    """Ends the run with a sentence for the screen; the run returns 1."""


def _on_stop_signal(signum: int, frame: FrameType | None) -> None:
    """Turns the first stop signal into KeyboardInterrupt and ignores the ones after it.

    Closing a Terminal window delivers SIGHUP twice within a millisecond: the shell sends it
    to the whole job (uv and the launcher) and uv forwards its own copy. A second
    KeyboardInterrupt would land inside the cleanup the first one started, where it could
    abort `stop_app` and leave the app running, or leave `Popen`'s internal lock held and
    hang the launcher. One request to stop is enough.
    """
    global _stopping
    if _stopping:
        return
    _stopping = True
    raise KeyboardInterrupt


def install_stop_signals() -> None:
    """Makes closing the window or pressing Ctrl+C stop the app too.

    The app runs in its own process group, so these signals reach only the launcher, which
    must pass them on to `stop_app`. SIGINT is set explicitly because a launcher started in
    the background of a non-interactive shell inherits it as ignored.
    """
    names = ("SIGINT", "SIGBREAK") if sys.platform == "win32" else ("SIGINT", "SIGTERM", "SIGHUP")
    for name in names:
        signal.signal(getattr(signal, name), _on_stop_signal)


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="launcher", description="Starts CV Generator.")
    parser.add_argument("--yes", action="store_true", help="install what is missing without asking")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--port", type=int, default=app.DEFAULT_PORT)
    return parser.parse_args(argv)


def _install_missing(args: argparse.Namespace, log: TextIO, log_path: Path) -> None:
    for item in prerequisites.required_prerequisites():
        if item.is_present():
            continue
        console.say(f"{item.name} is missing. {item.reason}")
        if item.install is None:
            raise _Failure(item.manual_help)
        if not console.ask("Install it now?", assume_yes=args.yes, read=lambda prompt: input(prompt)):
            raise _Failure(item.manual_help)
        if item.needs_admin and not prerequisites.ensure_admin():
            raise _Failure(f"Installing {item.name} needs an administrator password. {item.manual_help}")
        console.say(f"Installing {item.name}...")
        if not item.install(log) or not item.is_present():
            raise _Failure(f"Installing {item.name} did not work. The details are in {log_path}. {item.manual_help}")


def _run(args: argparse.Namespace, folder: Path, started: list[subprocess.Popen[bytes]]) -> int:
    """Returns 0 when the app is already running; otherwise opens a fresh log and starts it."""
    port = args.port
    url = app.app_url(port)
    console.say("Starting CV Generator...")

    # The port comes before the log: an app that is already running still writes to
    # start.log, and opening the log for a new run would wipe what it wrote.
    state = app.port_state(port)
    if state is app.PortState.OURS:
        console.say(f"CV Generator is already running at {url}.")
        if not args.no_browser:
            app.open_browser(url)
        return 0
    if state is app.PortState.OTHER:
        raise _Failure(
            f"Another program is using port {port}, so CV Generator cannot start. Close that program and try again."
        )

    try:
        log = console.open_log(folder)
    except OSError as error:
        raise _Failure(
            f"CV Generator cannot write in its own folder ({folder}). "
            "Move the folder somewhere you can write to, for example your Documents folder, and start it again."
        ) from error
    with log:
        _start(args, folder, log, started)


def _start(args: argparse.Namespace, folder: Path, log: TextIO, started: list[subprocess.Popen[bytes]]) -> NoReturn:
    """Prepares and starts the app, then waits for it; it only ends by raising."""
    log_path = folder / console.LOG_NAME
    port = args.port
    url = app.app_url(port)

    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise _Failure("uv was not found. Start CV Generator with start.command, start.sh or start.bat.")

    problem = prerequisites.folder_problem(folder)
    if problem:
        raise _Failure(problem)

    _install_missing(args, log, log_path)

    if not (folder / ".venv").exists():
        console.say(
            "The first start downloads the app's components and takes a few minutes. The next starts take seconds."
        )
    console.say("Preparing the app...")
    if not console.run_logged([uv, "sync", "--frozen"], log, cwd=folder):
        raise _Failure(
            "Preparing the app did not work. Check your internet connection and try again. "
            f"The details are in {log_path}."
        )
    if not console.run_logged(
        [uv, "run", "--frozen", "python", "-c", "import cv_generator, weasyprint"], log, cwd=folder
    ):
        raise _Failure(
            f"The libraries that draw the PDFs are installed but could not be loaded. The details are in {log_path}."
        )

    console.say("Starting the app...")
    process = app.start_app(app.app_command(uv, port), folder, log)
    started.append(process)
    ready = app.wait_until_ready(
        port, process, on_wait=lambda s: console.say(f"Still starting ({int(s // 60)} min)...")
    )
    if not ready:
        _stop_started(started)
        raise _Failure(f"CV Generator could not start. The details are in {log_path}.")

    opened = True if args.no_browser else app.open_browser(url)
    console.say(f"CV Generator is running at {url}")
    if not opened:
        console.say(f"Open {url} in your browser.")
    console.say("To stop it, close this window or press Ctrl+C.")

    process.wait()
    started.clear()
    raise _Failure(f"CV Generator stopped unexpectedly. The details are in {log_path}.")


def _stop_started(started: list[subprocess.Popen[bytes]]) -> None:
    """Stops every app this run started, however it got here.

    When the stop has another cause (the app never became ready, an unexpected error), the
    first stop signal can still land inside `stop_app`; stopping again finishes the job, and
    `_on_stop_signal` ignores every signal after that first one.
    """
    while started:
        process = started[0]
        try:
            app.stop_app(process)
        except KeyboardInterrupt:
            continue
        started.pop(0)


def main(argv: Sequence[str] | None = None, folder: Path = PROJECT_FOLDER) -> int:
    """Runs the launcher; returns the exit code."""
    global _stopping
    args = _parse(argv)
    started: list[subprocess.Popen[bytes]] = []
    # The KeyboardInterrupt of a stop signal is caught outside the failure handlers because
    # it can land while one of them runs; wherever it lands, what was started is stopped.
    try:
        try:
            install_stop_signals()
            return _run(args, folder, started)
        except _Failure as failure:
            console.say(str(failure))
            return 1
        except Exception:
            _stop_started(started)
            console.log_exception(folder)
            console.say(
                f"Something went wrong while starting CV Generator. The details are in {folder / console.LOG_NAME}."
            )
            return 1
    except KeyboardInterrupt:
        _stop_started(started)
        console.say("CV Generator stopped.")
        return 0
    finally:
        # Nothing is left to stop. A stop signal raised while Python exits would only put a
        # traceback on the screen.
        _stopping = True

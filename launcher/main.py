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
import traceback
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import TextIO

from launcher import app, console, prerequisites

PROJECT_FOLDER = Path(__file__).resolve().parent.parent


class _Failure(Exception):
    """Ends the run with a sentence for the screen; the run returns 1."""


def _raise_interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def install_stop_signals() -> None:
    """Makes closing the window or pressing Ctrl+C stop the app too.

    The app runs in its own process group, so these signals reach only the launcher, which
    must pass them on to `stop_app`. SIGINT is set explicitly because a launcher started in
    the background of a non-interactive shell inherits it as ignored.
    """
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, _raise_interrupt)
        return
    signal.signal(signal.SIGTERM, _raise_interrupt)
    signal.signal(signal.SIGHUP, _raise_interrupt)
    signal.signal(signal.SIGINT, signal.default_int_handler)


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
            raise _Failure(f"Installing {item.name} did not work. The details are in {log_path}.")


def _run(args: argparse.Namespace, folder: Path, log: TextIO, started: list[subprocess.Popen[bytes]]) -> int:
    log_path = folder / console.LOG_NAME
    port = args.port
    url = app.app_url(port)
    console.say("Starting CV Generator...")

    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise _Failure("uv was not found. Start CV Generator with start.command, start.sh or start.bat.")

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
        app.stop_app(process)
        started.clear()
        raise _Failure(f"CV Generator could not start. The details are in {log_path}.")

    opened = True if args.no_browser else app.open_browser(url)
    console.say(f"CV Generator is running at {url}")
    if not opened:
        console.say(f"Open {url} in your browser.")
    console.say("To stop it, close this window or press Ctrl+C.")

    process.wait()
    started.clear()
    raise _Failure(f"CV Generator stopped unexpectedly. The details are in {log_path}.")


def main(argv: Sequence[str] | None = None, folder: Path = PROJECT_FOLDER) -> int:
    """Runs the launcher; returns the exit code."""
    args = _parse(argv)
    install_stop_signals()
    started: list[subprocess.Popen[bytes]] = []
    with console.open_log(folder) as log:
        try:
            return _run(args, folder, log, started)
        except _Failure as failure:
            console.say(str(failure))
            return 1
        except KeyboardInterrupt:
            for process in started:
                app.stop_app(process)
            console.say("CV Generator stopped.")
            return 0
        except Exception:
            traceback.print_exc(file=log)
            console.say(
                f"Something went wrong while starting CV Generator. The details are in {folder / console.LOG_NAME}."
            )
            return 1

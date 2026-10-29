"""Starting the app, knowing when it is up, and stopping all of it.

The launcher runs Reflex in production mode on a single port: the compiled frontend and
the backend answer on the same address, so there is one port to check and one URL to open.
Everything here talks to `127.0.0.1` only.
"""

import contextlib
import http.client
import os
import signal
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import TextIO

DEFAULT_PORT = 3000
READY_TIMEOUT_SECONDS = 900  # the first start compiles the frontend, which takes minutes
STOP_GRACE_SECONDS = 15.0
# In production mode `GET /` serves this title. The dev server does not, so the title only
# marks "ours" for the app the launcher starts itself.
APP_TITLE = "<title>CV Generator</title>"

_HTTP_TIMEOUT_SECONDS = 5
_KILL_SETTLE_SECONDS = 2.0
_REAP_SECONDS = 1.0
_POLL_SECONDS = 1.0
_WAIT_REPORT_SECONDS = 60
_IS_WINDOWS = sys.platform == "win32"


class PortState(Enum):
    FREE = "free"
    OURS = "ours"
    OTHER = "other"


def _get(port: int, path: str) -> tuple[int, str]:
    """Does a GET on 127.0.0.1 and returns the status and the start of the body.

    `HTTPConnection("127.0.0.1", ...)` sends `Host: 127.0.0.1:<port>`, which the app's
    middleware allows (it refuses any Host other than localhost or 127.0.0.1).
    """
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=_HTTP_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read(1_000_000).decode("utf-8", errors="replace")
    finally:
        connection.close()


def port_state(port: int) -> PortState:
    """Tells whether `port` is free, held by this app, or held by another program."""
    try:
        status, body = _get(port, "/")
    except ConnectionRefusedError:
        return PortState.FREE
    except (OSError, http.client.HTTPException):
        # Something is listening but does not answer HTTP properly.
        return PortState.OTHER
    if status == http.HTTPStatus.OK and APP_TITLE in body:
        return PortState.OURS
    return PortState.OTHER


def app_url(port: int) -> str:
    return f"http://localhost:{port}"


def app_command(uv: str, port: int) -> list[str]:
    """The command that starts the app in production mode on one port.

    It goes through `python -m reflex` because `.venv/bin/reflex` has an absolute shebang
    that breaks when the project folder is moved, and `uv sync` does not repair it.
    """
    return [
        uv,
        "run",
        "--frozen",
        "python",
        "-m",
        "reflex",
        "run",
        "--env",
        "prod",
        "--single-port",
        "--frontend-port",
        str(port),
        "--backend-port",
        str(port),
    ]


def start_app(command: Sequence[str], folder: Path, log: TextIO) -> "subprocess.Popen[bytes]":
    """Starts the app with its output in the log, in its own process group.

    The group is what lets `stop_app` reach uv, Reflex, its workers and bun together,
    and keeps a Ctrl+C in the launcher's console from hitting them separately.
    """
    log.write(f"$ {' '.join(command)}\n")
    log.flush()
    group: dict[str, object] = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if _IS_WINDOWS else {"process_group": 0}
    )
    return subprocess.Popen(  # noqa: S603 - the command is built by app_command from constants
        list(command),
        cwd=folder,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        **group,  # type: ignore[arg-type]
    )


def wait_until_ready(
    port: int,
    process: "subprocess.Popen[bytes]",
    *,
    timeout: float = READY_TIMEOUT_SECONDS,
    on_wait: Callable[[float], None] | None = None,
) -> bool:
    """Polls `/ping` until it answers 200; False if the app exits or time runs out."""
    started = time.monotonic()
    next_report = _WAIT_REPORT_SECONDS
    while True:
        if process.poll() is not None:
            return False
        with contextlib.suppress(OSError, http.client.HTTPException):
            if _get(port, "/ping")[0] == http.HTTPStatus.OK:
                return True
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            return False
        if on_wait is not None and elapsed >= next_report:
            on_wait(elapsed)
            next_report += _WAIT_REPORT_SECONDS
        time.sleep(min(_POLL_SECONDS, max(timeout - elapsed, 0)))


def stop_app(process: "subprocess.Popen[bytes]", grace: float = STOP_GRACE_SECONDS) -> None:
    """Stops the app and everything it started, then reaps it.

    On POSIX SIGINT goes to the whole group (a plain SIGTERM does not stop Reflex), and
    SIGKILL follows if something is still alive after `grace` seconds. On Windows the
    tree is killed outright: the app saves atomically, so a hard stop is safe.

    Every wait is bounded, the last one too. CPython can run a signal handler right after
    `Popen.poll` (or a timed `wait`) takes its internal lock and before the `try` that
    releases it; a KeyboardInterrupt there leaves the lock held, and a plain `wait()` would
    then block the launcher forever. The app is dead by that point, and if this wait gives
    up, init reaps it once the launcher exits.
    """
    if _IS_WINDOWS:
        _kill_tree(process)
    else:
        _stop_group(process, grace)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=_REAP_SECONDS)


def _kill_tree(process: "subprocess.Popen[bytes]") -> None:
    """Kills the app's process tree on Windows.

    When taskkill fails (the leader already exited, so there is no tree to find from it, or
    taskkill is refused or missing), the leader is killed directly so at least it is gone.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed command, the pid is an int from our own child
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=STOP_GRACE_SECONDS,
        )
        killed = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        killed = False
    if not killed:
        with contextlib.suppress(OSError):
            process.kill()


def _stop_group(process: "subprocess.Popen[bytes]", grace: float) -> None:
    """Sends SIGINT to the app's process group, then SIGKILL after `grace` seconds."""
    group = process.pid  # process_group=0 makes the child the leader of its own group
    process.poll()  # reap a leader that already exited, so the signals below have a live target
    _signal_group(group, signal.SIGINT)
    deadline = time.monotonic() + grace
    while _group_alive(process, group):
        if time.monotonic() >= deadline:
            _signal_group(group, signal.SIGKILL)
            _wait_for_group(process, group, _KILL_SETTLE_SECONDS)
            break
        time.sleep(0.05)


def _signal_group(group: int, sig: signal.Signals) -> None:
    """Sends `sig` to the group. A group that is gone, or that macOS refuses (EPERM:
    only zombies or exiting processes left), has nothing to receive it; the caller's
    wait decides when the group is really gone."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(group, sig)


def _wait_for_group(process: "subprocess.Popen[bytes]", group: int, seconds: float) -> None:
    """Waits (bounded) until the group is gone; SIGKILL is delivered, not instant.

    Returning earlier would let a caller restart the app while a dying member still holds
    its port.
    """
    deadline = time.monotonic() + seconds
    while _group_alive(process, group) and time.monotonic() < deadline:
        time.sleep(0.02)


def _group_alive(process: "subprocess.Popen[bytes]", group: int) -> bool:
    """True while any process of the group exists.

    The leader is reaped first: a zombie leader still counts as a member of the group.
    Only "no such group" counts as gone.
    """
    process.poll()
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # On macOS EPERM means the group still has members, only zombies or processes in
        # the middle of exiting (leader or not). Their sockets may not be closed yet, so it
        # is not "gone": keep waiting. Only ProcessLookupError ends it. Every wait is
        # bounded, and init reaps the orphans, after which the group disappears.
        return True
    return True


def open_browser(url: str) -> bool:
    """Opens `url` in the default browser; False when that is not possible."""
    try:
        return webbrowser.open(url)
    except Exception:  # noqa: BLE001 - whatever the platform does, the app still works without it
        return False

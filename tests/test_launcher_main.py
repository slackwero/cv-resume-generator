import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import FrameType

import pytest

from launcher import app, console, prerequisites
from launcher import main as launcher_main
from launcher.main import install_stop_signals, main

Handler = Callable[[int, FrameType | None], object]


class FakeProcess:
    """Stands in for the app's process: `wait()` returns a code or raises."""

    def __init__(self, outcome: int | type[BaseException] = KeyboardInterrupt) -> None:
        self.outcome = outcome

    def wait(self) -> int:
        if isinstance(self.outcome, int):
            return self.outcome
        raise self.outcome


class Calls:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.stopped: list[object] = []
        self.commands: list[list[str]] = []


def present(name: str = "Pango") -> prerequisites.Prerequisite:
    return prerequisites.Prerequisite(
        name=name,
        reason="PDFs need it.",
        manual_help="Do it by hand.",
        is_present=lambda: True,
        install=None,
    )


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """Replaces every external call, so no test starts an app, installs or opens a browser."""
    seen = Calls()
    monkeypatch.setenv("UV", "/x/uv")
    monkeypatch.setattr(launcher_main, "install_stop_signals", lambda: None)
    monkeypatch.setattr(app, "port_state", lambda port: app.PortState.FREE)
    monkeypatch.setattr(prerequisites, "folder_problem", lambda folder: None)
    monkeypatch.setattr(prerequisites, "required_prerequisites", lambda: [present()])

    def fake_run_logged(command, log, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen.commands.append(list(command))
        return True

    def fake_open(url: str) -> bool:
        seen.opened.append(url)
        return True

    monkeypatch.setattr(console, "run_logged", fake_run_logged)
    monkeypatch.setattr(
        app, "start_app", lambda command, folder, log: seen.commands.append(list(command)) or FakeProcess()
    )
    monkeypatch.setattr(app, "wait_until_ready", lambda port, process, **kwargs: True)
    monkeypatch.setattr(app, "stop_app", lambda process, *args, **kwargs: seen.stopped.append(process))
    monkeypatch.setattr(app, "open_browser", fake_open)
    return seen


def test_an_app_already_running_only_opens_the_browser(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app, "port_state", lambda port: app.PortState.OURS)

    def no_start(*args: object, **kwargs: object) -> None:
        raise AssertionError("must not start a second app")

    monkeypatch.setattr(app, "start_app", no_start)
    assert main(["--port", "3100"], folder=tmp_path) == 0
    assert calls.opened == ["http://localhost:3100"]


def test_another_program_on_the_port_is_named_plainly(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "port_state", lambda port: app.PortState.OTHER)
    assert main(["--port", "3100"], folder=tmp_path) == 1
    assert "Another program is using port 3100" in capsys.readouterr().out


def test_uv_missing_is_reported(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("UV")
    monkeypatch.setattr(launcher_main.shutil, "which", lambda name: None)
    assert main([], folder=tmp_path) == 1
    assert "uv was not found" in capsys.readouterr().out


def test_a_folder_inside_onedrive_stops_before_anything_is_installed(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden() -> None:
        raise AssertionError("nothing may be checked or installed")

    monkeypatch.setattr(prerequisites, "folder_problem", lambda folder: "Move it.")
    monkeypatch.setattr(prerequisites, "required_prerequisites", forbidden)
    assert main([], folder=tmp_path) == 1
    assert "Move it." in capsys.readouterr().out


def missing(install, *, needs_admin: bool = False) -> prerequisites.Prerequisite:  # noqa: ANN001
    return prerequisites.Prerequisite(
        name="Pango",
        reason="PDFs need it.",
        manual_help="Do it by hand.",
        is_present=lambda: False,
        install=install,
        needs_admin=needs_admin,
    )


def test_declining_an_install_explains_how_to_do_it_by_hand(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(log: object) -> bool:
        raise AssertionError("must not install without a yes")

    monkeypatch.setattr(prerequisites, "required_prerequisites", lambda: [missing(forbidden)])
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert main([], folder=tmp_path) == 1
    out = capsys.readouterr().out
    assert "Pango is missing. PDFs need it." in out
    assert "Do it by hand." in out


def test_a_prerequisite_without_an_installer_gives_the_manual_help(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(prerequisites, "required_prerequisites", lambda: [missing(None)])
    assert main(["--yes"], folder=tmp_path) == 1
    assert "Do it by hand." in capsys.readouterr().out


def test_an_install_that_needs_a_password_that_is_refused_stops(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(prerequisites, "required_prerequisites", lambda: [missing(lambda log: True, needs_admin=True)])
    monkeypatch.setattr(prerequisites, "ensure_admin", lambda: False)
    assert main(["--yes"], folder=tmp_path) == 1
    out = capsys.readouterr().out
    assert "Installing Pango needs an administrator password." in out
    assert "Do it by hand." in out


def test_a_failed_install_points_to_the_log(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(prerequisites, "required_prerequisites", lambda: [missing(lambda log: False)])
    assert main(["--yes"], folder=tmp_path) == 1
    out = capsys.readouterr().out
    assert "Installing Pango did not work." in out
    assert str(tmp_path / "start.log") in out


def test_an_install_that_leaves_it_missing_is_a_failure(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(prerequisites, "required_prerequisites", lambda: [missing(lambda log: True)])
    assert main(["--yes"], folder=tmp_path) == 1
    assert "Installing Pango did not work." in capsys.readouterr().out


def test_the_first_start_warns_that_it_is_slow(
    calls: Calls, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([], folder=tmp_path)
    assert "takes a few minutes" in capsys.readouterr().out


def test_a_later_start_does_not_warn(calls: Calls, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".venv").mkdir()
    main([], folder=tmp_path)
    assert "takes a few minutes" not in capsys.readouterr().out


def test_a_failed_sync_points_to_the_connection(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "run_logged", lambda command, log, **kwargs: False)
    assert main([], folder=tmp_path) == 1
    assert "Check your internet connection" in capsys.readouterr().out


def test_pdf_libraries_that_do_not_load_are_reported(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    results = iter([True, False])
    monkeypatch.setattr(console, "run_logged", lambda command, log, **kwargs: next(results))
    assert main([], folder=tmp_path) == 1
    assert "could not be loaded" in capsys.readouterr().out


def test_a_normal_start_opens_the_browser_and_stops_on_ctrl_c(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProcess()
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: fake)
    assert main(["--port", "3100"], folder=tmp_path) == 0
    out = capsys.readouterr().out
    assert calls.opened == ["http://localhost:3100"]
    assert calls.stopped == [fake]
    assert "CV Generator is running at http://localhost:3100" in out
    assert "To stop it, close this window or press Ctrl+C." in out
    assert "CV Generator stopped." in out


def test_the_commands_are_the_documented_ones(calls: Calls, tmp_path: Path) -> None:
    main([], folder=tmp_path)
    assert calls.commands[0] == ["/x/uv", "sync", "--frozen"]
    assert calls.commands[1] == ["/x/uv", "run", "--frozen", "python", "-c", "import cv_generator, weasyprint"]


def test_a_browser_that_does_not_open_tells_the_person_the_address(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "open_browser", lambda url: False)
    main([], folder=tmp_path)
    assert "Open http://localhost:3000 in your browser." in capsys.readouterr().out


def test_an_app_that_never_becomes_ready_is_stopped_and_reported(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProcess()
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: fake)
    monkeypatch.setattr(app, "wait_until_ready", lambda port, process, **kwargs: False)
    assert main([], folder=tmp_path) == 1
    assert calls.stopped == [fake]
    assert "could not start" in capsys.readouterr().out


def test_ctrl_c_while_the_app_is_starting_stops_it(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeProcess()
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: fake)

    def interrupted(port: int, process: object, **kwargs: object) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr(app, "wait_until_ready", interrupted)
    assert main([], folder=tmp_path) == 0
    assert calls.stopped == [fake]


def test_ctrl_c_before_the_app_exists_has_nothing_to_stop(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted(command: object, log: object, **kwargs: object) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr(console, "run_logged", interrupted)
    assert main([], folder=tmp_path) == 0
    assert calls.stopped == []
    assert "CV Generator stopped." in capsys.readouterr().out


def test_an_app_that_dies_is_reported(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: FakeProcess(1))
    assert main([], folder=tmp_path) == 1
    assert "stopped unexpectedly" in capsys.readouterr().out


def test_an_unexpected_error_is_explained_on_screen_and_detailed_in_the_log(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(port: int) -> app.PortState:
        raise OSError("boom")

    monkeypatch.setattr(app, "port_state", boom)
    assert main([], folder=tmp_path) == 1
    out = capsys.readouterr().out
    assert "Something went wrong" in out
    assert "Traceback" not in out
    assert "boom" in (tmp_path / "start.log").read_text(encoding="utf-8")


def test_no_browser_keeps_the_browser_closed(calls: Calls, tmp_path: Path) -> None:
    assert main(["--no-browser"], folder=tmp_path) == 0
    assert calls.opened == []


def installed_handlers(monkeypatch: pytest.MonkeyPatch) -> dict[int, Handler]:
    """Runs the real `install_stop_signals` with `signal.signal` replaced, so pytest keeps its own handlers."""
    installed: dict[int, Handler] = {}
    monkeypatch.setattr(signal, "signal", lambda number, handler: installed.update({number: handler}))
    monkeypatch.setattr(launcher_main, "_stopping", False, raising=False)
    install_stop_signals()
    return installed


def interrupts(handler: Handler, number: int) -> bool:
    """Calls a signal handler the way Python would; True when it raised KeyboardInterrupt."""
    frame: FrameType | None = None
    try:
        handler(number, frame)
    except KeyboardInterrupt:
        return True
    return False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_closing_the_window_interrupts_once_and_lets_the_stop_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shell sends SIGHUP to the whole job and uv forwards its copy a moment later.

    Only the first may interrupt: a second KeyboardInterrupt would land inside the cleanup the
    first one started and leave the app running.
    """
    handlers = installed_handlers(monkeypatch)
    assert set(handlers) == {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
    try:
        handlers[signal.SIGHUP](signal.SIGHUP, None)
    except KeyboardInterrupt:
        # uv's copy arrives while the first one is still being handled
        assert not interrupts(handlers[signal.SIGHUP], signal.SIGHUP)
    else:
        pytest.fail("the first stop signal must interrupt the launcher")
    for number in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        assert not interrupts(handlers[number], number)


def test_on_windows_ctrl_c_and_ctrl_break_interrupt_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher_main.sys, "platform", "win32")
    monkeypatch.setattr(signal, "SIGBREAK", 21, raising=False)
    handlers = installed_handlers(monkeypatch)
    assert set(handlers) == {signal.SIGINT, 21}
    assert interrupts(handlers[21], 21)
    assert not interrupts(handlers[21], 21)
    assert not interrupts(handlers[signal.SIGINT], signal.SIGINT)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_a_stop_signal_after_the_run_is_over_is_ignored(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Raised while Python exits, it would only put a traceback on screen."""
    handlers = installed_handlers(monkeypatch)
    monkeypatch.setattr(app, "port_state", lambda port: app.PortState.OTHER)
    assert main([], folder=tmp_path) == 1
    assert not interrupts(handlers[signal.SIGHUP], signal.SIGHUP)


def test_a_stop_signal_while_an_error_is_reported_still_stops_the_app(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProcess()
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: fake)

    def broken(url: str) -> bool:
        raise RuntimeError("no browser")

    real_say = console.say

    def closed_while_reporting(message: str) -> None:
        if message.startswith("Something went wrong"):
            raise KeyboardInterrupt  # the window was closed right then
        real_say(message)

    monkeypatch.setattr(app, "open_browser", broken)
    monkeypatch.setattr(console, "say", closed_while_reporting)
    try:
        code = main([], folder=tmp_path)
    except KeyboardInterrupt:
        pytest.fail("the stop signal escaped the launcher, with a traceback")
    assert code == 0
    assert calls.stopped == [fake]
    assert "CV Generator stopped." in capsys.readouterr().out


def test_the_module_runs_as_a_program(tmp_path: Path) -> None:
    # A bad port must be rejected by the argument parser before anything starts.
    result = subprocess.run(  # noqa: S603 - constant command
        [sys.executable, "-m", "launcher", "--port", "not-a-number"],
        capture_output=True,
        cwd=Path(__file__).resolve().parent.parent,
        check=False,
    )
    assert result.returncode == 2


def test_an_error_after_the_app_started_still_stops_it(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProcess()
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: fake)

    def broken(url: str) -> bool:
        raise RuntimeError("no browser")

    monkeypatch.setattr(app, "open_browser", broken)
    assert main([], folder=tmp_path) == 1
    assert calls.stopped == [fake]
    assert "Something went wrong" in capsys.readouterr().out


def test_a_second_ctrl_c_while_stopping_does_not_abort_the_stop(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeProcess()
    monkeypatch.setattr(app, "start_app", lambda command, folder, log: fake)
    attempts: list[object] = []

    def impatient(process: object, *args: object, **kwargs: object) -> None:
        attempts.append(process)
        if len(attempts) == 1:
            raise KeyboardInterrupt
        calls.stopped.append(process)

    monkeypatch.setattr(app, "stop_app", impatient)
    assert main([], folder=tmp_path) == 0
    assert calls.stopped == [fake]
    out = capsys.readouterr().out
    assert "CV Generator stopped." in out
    assert "Traceback" not in out


def test_a_folder_that_cannot_be_written_is_explained_plainly(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def denied(folder: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(console, "open_log", denied)
    assert main([], folder=tmp_path) == 1
    out = capsys.readouterr().out
    assert f"CV Generator cannot write in its own folder ({tmp_path})." in out
    assert "Traceback" not in out

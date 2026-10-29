import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO

import pytest

from launcher.app import (
    PortState,
    app_command,
    app_url,
    open_browser,
    port_state,
    start_app,
    stop_app,
    wait_until_ready,
)

SERVE = Callable[[str], int]


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        result = subprocess.run(  # noqa: S603 - constant command, the pid is an int
            ["tasklist", "/FI", f"PID eq {pid}"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_file(path: Path, seconds: float = 10) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"{path} was never written")


@pytest.fixture
def serve() -> Iterator[SERVE]:
    """Serves one body for every path (and `pong` for /ping) on a free local port."""
    servers: list[ThreadingHTTPServer] = []

    def start(body: str) -> int:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
                payload = b"pong" if self.path == "/ping" else body.encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server.server_address[1]

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def raw_socket_that_closes() -> Iterator[int]:
    """A listener that accepts and hangs up without speaking HTTP."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    stop = threading.Event()

    def accept() -> None:
        listener.settimeout(0.1)
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except OSError:
                continue
            connection.close()

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield listener.getsockname()[1]
    stop.set()
    thread.join()
    listener.close()


@pytest.fixture
def log(tmp_path: Path) -> Iterator[TextIO]:
    with (tmp_path / "start.log").open("w", encoding="utf-8") as handle:
        yield handle


def test_a_closed_port_is_free() -> None:
    assert port_state(unused_port()) is PortState.FREE


def test_the_app_is_recognised_by_its_title(serve: SERVE) -> None:
    assert port_state(serve("<html><head><title>CV Generator</title></head></html>")) is PortState.OURS


def test_another_web_app_is_another_program(serve: SERVE) -> None:
    assert port_state(serve("<html><head><title>Grafana</title></head></html>")) is PortState.OTHER


def test_something_that_is_not_http_is_another_program(raw_socket_that_closes: int) -> None:
    assert port_state(raw_socket_that_closes) is PortState.OTHER


def test_the_url_uses_localhost() -> None:
    assert app_url(3100) == "http://localhost:3100"


def test_the_app_runs_as_a_module_so_a_moved_folder_still_starts() -> None:
    assert app_command("/x/uv", 3100) == [
        "/x/uv",
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
        "3100",
        "--backend-port",
        "3100",
    ]


def test_ready_when_ping_answers(serve: SERVE, tmp_path: Path, log: TextIO) -> None:
    port = serve("whatever")
    process = start_app([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, log)
    try:
        assert wait_until_ready(port, process, timeout=10) is True
    finally:
        stop_app(process)


def test_not_ready_when_the_app_exits(tmp_path: Path, log: TextIO) -> None:
    process = start_app([sys.executable, "-c", "pass"], tmp_path, log)
    started = time.monotonic()
    assert wait_until_ready(unused_port(), process) is False
    assert time.monotonic() - started < 5
    stop_app(process)


def test_not_ready_after_the_timeout(tmp_path: Path, log: TextIO) -> None:
    process = start_app([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, log)
    try:
        started = time.monotonic()
        assert wait_until_ready(unused_port(), process, timeout=1) is False
        assert time.monotonic() - started < 5
    finally:
        stop_app(process)


def test_stop_app_stops_the_whole_tree(tmp_path: Path, log: TextIO) -> None:
    pid_file = tmp_path / "grandchild.pid"
    child_code = (
        "import subprocess, sys, time\n"
        "grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(grandchild.pid))\n"
        "time.sleep(60)\n"
    )
    process = start_app([sys.executable, "-c", child_code], tmp_path, log)
    grandchild = int(wait_for_file(pid_file))
    stop_app(process)
    assert not pid_alive(process.pid)
    deadline = time.monotonic() + 5
    while pid_alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not pid_alive(grandchild)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT is a POSIX signal")
def test_stop_app_stops_a_tree_that_ignores_ctrl_c(tmp_path: Path, log: TextIO) -> None:
    ready = tmp_path / "ready"
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        f"open({str(ready)!r}, 'w').write('x')\n"
        "time.sleep(60)\n"
    )
    process = start_app([sys.executable, "-c", code], tmp_path, log)
    wait_for_file(ready)
    started = time.monotonic()
    stop_app(process, grace=1)
    assert time.monotonic() - started < 5
    assert not pid_alive(process.pid)


def test_open_browser_reports_failure_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(url: str) -> bool:
        raise RuntimeError(url)

    monkeypatch.setattr("launcher.app.webbrowser.open", boom)
    assert open_browser("http://localhost:1") is False

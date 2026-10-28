"""Checks the local-only protection against the running app, not against a test client.

The unit tests exercise the middleware in isolation; this script proves that the real
server (granian, bound by `rxconfig.py`) behaves the same way. Start the app first
(`uv run reflex run`), then run it with the ports the app uses:

    uv run python scripts/smoke_local_only.py [--frontend-port 3000] [--backend-port 8000]

The checks: the app answers, a foreign Host is refused, a foreign Origin is refused, a
foreign websocket handshake is refused, and the backend is not reachable from the network.

It prints one line per check (`PASS`, `FAIL` or `SKIP`) and exits 0 only when no check
failed. CI runs it after starting the app, so the first start (which installs the
frontend) can take minutes: it polls the health endpoint until `--timeout` runs out.
"""

import argparse
import base64
import ipaddress
import os
import socket
import sys
import time

import httpx

LOOPBACK = "127.0.0.1"
# Reserved for documentation (RFC 5737): routable on paper, so the OS picks the outgoing
# interface for it, but nobody answers and no packet is sent by a UDP connect().
TEST_NET_ADDRESS = "192.0.2.1"
POLL_INTERVAL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 5
CONNECT_TIMEOUT_SECONDS = 3


def wait_for_app(ping_url: str, timeout: float) -> bool:
    """Poll the health endpoint until it answers with anything, or the timeout runs out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx.get(ping_url, timeout=REQUEST_TIMEOUT_SECONDS)
        except httpx.HTTPError:
            time.sleep(POLL_INTERVAL_SECONDS)
        else:
            return True
    return False


def status_of(ping_url: str, headers: dict[str, str]) -> int | str:
    """Status code of GET /ping with the given headers, or the error that prevented one."""
    try:
        return httpx.get(ping_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS).status_code
    except httpx.HTTPError as error:
        return f"{type(error).__name__}: {error}"


def expect_status(name: str, ping_url: str, headers: dict[str, str], expected: int) -> bool:
    """Report one check that passes when /ping answers `expected` to the given headers."""
    actual = status_of(ping_url, headers)
    if actual == expected:
        print(f"PASS {name}")
        return True
    print(f"FAIL {name}: expected {expected}, got {actual}")
    return False


def outbound_ipv4() -> str | None:
    """This machine's address on the network, found without sending anything."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect((TEST_NET_ADDRESS, 9))
            return probe.getsockname()[0]
        except OSError:
            return None


def check_not_reachable_from_network(backend_port: int) -> bool:
    """The backend must refuse (or ignore) connections that arrive on the network address."""
    name = "not reachable from the network"
    address = outbound_ipv4()
    if address is None or ipaddress.ip_address(address).is_loopback:
        print(f"SKIP {name}: this machine has no non-loopback IPv4 address")
        return True
    try:
        socket.create_connection((address, backend_port), timeout=CONNECT_TIMEOUT_SECONDS).close()
    except OSError:
        print(f"PASS {name}")
        return True
    print(f"FAIL {name}: {address}:{backend_port} accepted a connection")
    return False


def check_foreign_websocket_refused(backend_port: int) -> bool:
    """A websocket upgrade from a foreign Origin must be answered with a 403.

    The websocket carries every app event, so this is the door that matters most. The ASGI
    unit tests cover the close code; this proves that the real server turns it into a 403
    handshake. A raw socket is used because an HTTP client would not send the upgrade.
    """
    name = "foreign websocket refused"
    request = (
        "GET /_event/?EIO=4&transport=websocket HTTP/1.1\r\n"
        f"Host: localhost:{backend_port}\r\n"
        "Origin: http://evil.example\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
        "\r\n"
    )
    try:
        with socket.create_connection((LOOPBACK, backend_port), timeout=CONNECT_TIMEOUT_SECONDS) as connection:
            connection.settimeout(REQUEST_TIMEOUT_SECONDS)
            connection.sendall(request.encode("ascii"))
            status_line = connection.recv(1024).split(b"\r\n", 1)[0].decode("latin-1")
    except OSError as error:
        print(f"FAIL {name}: {type(error).__name__}: {error}")
        return False
    if status_line.split(" ")[1:2] == ["403"]:
        print(f"PASS {name}")
        return True
    print(f"FAIL {name}: expected a 403 status line, got {status_line!r}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the local-only protection of the running app.")
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=300, help="seconds to wait for the app to start")
    args = parser.parse_args()

    ping_url = f"http://{LOOPBACK}:{args.backend_port}/ping"
    own_page = {"Origin": f"http://localhost:{args.frontend_port}"}

    if not wait_for_app(ping_url, args.timeout):
        print(f"FAIL app answers: no response from {ping_url} within {args.timeout:g} seconds")
        return 1

    results = [
        expect_status("app answers", ping_url, own_page, 200),
        expect_status("foreign host refused", ping_url, {"Host": "evil.example"}, 403),
        expect_status("foreign origin refused", ping_url, {"Origin": "http://evil.example"}, 403),
        check_foreign_websocket_refused(args.backend_port),
        check_not_reachable_from_network(args.backend_port),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

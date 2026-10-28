"""Checks the local-only protection against the running app, not against a test client.

The unit tests exercise the middleware in isolation; this script proves that the real
server (granian, bound by `rxconfig.py`) behaves the same way. Start the app first
(`uv run reflex run`), then run it with the ports the app uses:

    uv run python scripts/smoke_local_only.py [--frontend-port 3000] [--backend-port 8000]

It prints one line per check (`PASS`, `FAIL` or `SKIP`) and exits 0 only when no check
failed. CI runs it after starting the app, so the first start (which installs the
frontend) can take minutes: it polls the health endpoint until `--timeout` runs out.
"""

import argparse
import ipaddress
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
        check_not_reachable_from_network(args.backend_port),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

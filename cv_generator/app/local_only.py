"""Rules that keep the app reachable only from this computer and from its own page.

The app has no login: whoever reaches the backend can read and rewrite the profile. Two
things could still reach it from a browser on this very machine:

- Other websites. A page open in another tab can make the browser call
  `http://localhost:8000`. The browser always sends an `Origin` header in that case, so
  an Origin that is not the app's own page is refused.
- DNS rebinding. A hostile domain is pointed at 127.0.0.1 after the page loads, so the
  browser treats the backend as the same origin and sends no `Origin` at all. What gives
  it away is the `Host` header, which still carries the hostile domain.

The ports are read at request time, not at import: `reflex run` exports the real
frontend and backend ports to the backend process as environment variables only when it
starts, so the config says the right thing only then.

The middleware is pure ASGI, not `BaseHTTPMiddleware`, because that one does not see
websockets, and the app's events travel through the socket.io websocket.
"""

from collections.abc import Callable, Collection
from urllib.parse import urlsplit

from reflex.config import get_config
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1"})

REFUSAL_MESSAGE = "CV Generator only accepts connections from this computer."
WEBSOCKET_POLICY_VIOLATION = 1008


def is_local_host(host: str | None) -> bool:
    """Whether a `Host` header names this computer, whatever the port."""
    if not host:
        return False
    try:
        return urlsplit("//" + host).hostname in LOCAL_HOSTNAMES
    except ValueError:
        return False


def is_allowed_origin(origin: str | None, ports: Collection[int]) -> bool:
    """Whether an `Origin` header is one of the app's own pages.

    `None` means the header was not sent (the browser does not send it on same-origin
    GETs, nor do non-browser clients), which is allowed. An empty string is a header
    that was sent with nothing in it, which is not.
    """
    if origin is None:
        return True
    try:
        parts = urlsplit(origin)
        # `.port` raises ValueError on a malformed port: that is a refusal, not a crash.
        return parts.scheme == "http" and parts.hostname in LOCAL_HOSTNAMES and parts.port in ports
    except ValueError:
        return False


def configured_ports() -> frozenset[int]:
    """The frontend and backend ports of the running app."""
    config = get_config()
    return frozenset({config.frontend_port, config.backend_port})


class LocalOnlyMiddleware:
    """Refuses HTTP and websocket connections that fail the host and origin rules."""

    def __init__(self, app: ASGIApp, ports: Callable[[], Collection[int]] = configured_ports) -> None:
        self._app = app
        self._ports = ports

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Lifespan has no headers and nothing to protect: it goes straight through.
        if scope["type"] not in ("http", "websocket") or self._is_allowed(scope):
            await self._app(scope, receive, send)
        elif scope["type"] == "http":
            await PlainTextResponse(REFUSAL_MESSAGE, status_code=403)(scope, receive, send)
        else:
            # Closing before accepting makes the server answer the handshake with 403.
            await send({"type": "websocket.close", "code": WEBSOCKET_POLICY_VIOLATION})

    def _is_allowed(self, scope: Scope) -> bool:
        headers = {name.decode("latin-1"): value.decode("latin-1") for name, value in scope["headers"]}
        return is_local_host(headers.get("host")) and is_allowed_origin(headers.get("origin"), self._ports())

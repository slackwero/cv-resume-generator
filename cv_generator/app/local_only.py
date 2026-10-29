"""Rules that keep the app reachable only from this computer and from its own page.

The app has no login: whoever reaches the backend can read and rewrite the profile. Two
things could still reach it from a browser on this very machine:

- Other websites. A page open in another tab can make the browser call
  `http://localhost:8000`. fetch/XHR, form POSTs and websocket handshakes carry an
  `Origin` header, and one that is not the app's own page is refused. Cross-site GETs
  (images, iframes, scripts, navigations, and `fetch()` in no-cors mode) carry no
  `Origin`, but modern browsers mark every one of them with `Sec-Fetch-Site:
  cross-site`, and that is what refuses them. The one exception is a top-level
  navigation (`Sec-Fetch-Mode: navigate`, `Sec-Fetch-Dest: document`, GET or HEAD),
  which is what clicking a link to the app on another website does: it replaces the
  page, so the other site cannot read the response, and GETs never change state.
  Iframes still carry `Sec-Fetch-Dest: iframe` and are refused.
- DNS rebinding. A hostile domain is pointed at 127.0.0.1 after the page loads, so the
  browser treats the backend as the same origin. Its requests still carry the hostile
  domain in the `Host` header, which is what gives it away; the `Origin` rule also
  catches its POSTs and websocket handshakes.

A request with neither `Origin` nor `Sec-Fetch-Site` (curl, very old browsers) passes on
the Host rule alone. That is why no backend GET may ever change state.

Do not read a 200 on a foreign CORS preflight (`OPTIONS`) as a hole. Reflex wraps the
transformed app in its own outer Starlette `CORSMiddleware` (`allow_origins=*`, with
credentials), which answers preflights before this middleware sees them. The real
request that follows still reaches this middleware and gets a 403, so the app's handler
never runs.

Known limit: in development mode the frontend is served by Vite on port 3000, outside
this middleware, so another website can frame the live app in an iframe (clickjacking:
it cannot read anything, only trick clicks). In the prod single-port mode the frontend
is served through this middleware, so cross-site iframes are refused.

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


def is_allowed_fetch_site(fetch_site: str | None) -> bool:
    """Whether a `Sec-Fetch-Site` header says the request is not from another site.

    `None` (curl, old browsers), `same-origin`, `same-site` and `none` (a typed URL or a
    bookmark) are allowed; only `cross-site` is refused.
    """
    return (fetch_site or "").lower() != "cross-site"


def is_top_level_navigation(method: str | None, fetch_mode: str | None, fetch_dest: str | None) -> bool:
    """Whether a request is a browser navigating a whole tab to the app, as a link click does.

    Only GET and HEAD count, and `Sec-Fetch-Dest: document` keeps iframes (`iframe`,
    `frame`, `embed`, `object`) out. Websocket scopes have no method: they never count.
    """
    return (
        (method or "").upper() in ("GET", "HEAD")
        and (fetch_mode or "").lower() == "navigate"
        and (fetch_dest or "").lower() == "document"
    )


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
        if not is_local_host(headers.get("host")):
            return False
        origin = headers.get("origin")
        if origin is None:
            # Without an Origin (a plain cross-site GET), Fetch Metadata tells who is calling.
            fetch_site = headers.get("sec-fetch-site")
            return is_allowed_fetch_site(fetch_site) or is_top_level_navigation(
                scope.get("method"), headers.get("sec-fetch-mode"), headers.get("sec-fetch-dest")
            )
        return is_allowed_origin(origin, self._ports())

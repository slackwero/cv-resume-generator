"""A key every request to the backend carries, which only the app's owner can read.

The app has no login. LocalOnlyMiddleware refuses other computers and other websites, but
any program on this computer reached the backend: on a shared computer another account
could open the websocket and read the profile, or upload a file and read the review. As in
Jupyter, the app asks for a key. It is kept in `data/access.key`, which only the account
that runs the app can read (private_files.py), and the link the backend prints when it
starts, which the launcher opens by itself, trades it for a cookie that the browser sends
with every request after that, for a year.

The cookie is HttpOnly: cookies do not tell ports apart, so a page from any other program
on 127.0.0.1 could read one that scripts could. It is SameSite=Lax: other websites'
requests never carry it, but a link from one still opens the app, and a GET changes
nothing. To change the key, delete the file: the next start makes another.
"""

import contextlib
import functools
import hmac
import os
import secrets
import tempfile
from collections.abc import Callable
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

from reflex.config import get_config
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from cv_generator.app.config import DATA_DIR

KEY_FILE_NAME = "access.key"
COOKIE_NAME = "cv_generator_key"
ACCESS_PATH = "/_access"
KEY_PARAMETER = "key"
COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60
# A shorter key in the file is a damaged one: an empty key would let an empty cookie in.
MIN_KEY_LENGTH = 32
# What answers without the key, because it says nothing about you: the launcher and the
# smoke test poll /ping before anyone has the key, and in development the page, on another
# port, checks the backend's health and routes without sending cookies.
OPEN_PATHS = frozenset({"/ping", "/_health", "/_all_routes"})
DEFAULT_PORTS = {"frontend": 3000, "backend": 8000}
WEBSOCKET_POLICY_VIOLATION = 1008
MISSING_KEY_MESSAGE = (
    "CV Generator needs its key. Open the link it printed when it started; the launcher opens "
    f"it for you. The key is in data/{KEY_FILE_NAME}, and the link is "
    f"http://127.0.0.1:<the app's port>{ACCESS_PATH}?{KEY_PARAMETER}=<the key>."
)


def load_or_create_key(data_dir: Path) -> str:
    """The app's key, created the first time, in a file only its owner can read (0600)."""
    path = data_dir / KEY_FILE_NAME
    with contextlib.suppress(OSError):
        key = path.read_text(encoding="utf-8").strip()
        if len(key) >= MIN_KEY_LENGTH:
            return key
    key = secrets.token_urlsafe(32)
    # mkstemp creates the file 0600, and the rename makes a half-written key impossible.
    descriptor, temporary = tempfile.mkstemp(dir=data_dir, prefix=f".{KEY_FILE_NAME}.")
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(key)
    Path(temporary).replace(path)
    return key


def access_link(port: int, key: str) -> str:
    """The link that trades the key for the cookie and opens the app."""
    return f"http://127.0.0.1:{port}{ACCESS_PATH}?{KEY_PARAMETER}={key}"


@functools.cache
def app_key() -> str:
    return load_or_create_key(DATA_DIR)


def frontend_url() -> str:
    return f"http://127.0.0.1:{get_config().frontend_port or DEFAULT_PORTS['frontend']}"


def announce_access() -> None:
    """Prints the link with the key when the backend starts: with `reflex run`, it is the one to open."""
    port = get_config().backend_port or DEFAULT_PORTS["backend"]
    print(f"Open CV Generator with its key: {access_link(port, app_key())}", flush=True)


class AccessKeyMiddleware:
    """Refuses HTTP and websocket connections that do not carry the app's key."""

    def __init__(
        self, app: ASGIApp, key: Callable[[], str] = app_key, frontend: Callable[[], str] = frontend_url
    ) -> None:
        self._app = app
        self._key = key
        self._frontend = frontend

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or (scope["type"] == "http" and scope["path"] in OPEN_PATHS):
            await self._app(scope, receive, send)
        elif scope["type"] == "http" and scope["path"] == ACCESS_PATH:
            await self._trade(scope, receive, send)
        elif self._matches(self._cookie(scope)):
            await self._app(scope, receive, send)
        elif scope["type"] == "http":
            await PlainTextResponse(MISSING_KEY_MESSAGE, status_code=403)(scope, receive, send)
        else:
            # Closing before accepting makes the server answer the handshake with 403.
            await send({"type": "websocket.close", "code": WEBSOCKET_POLICY_VIOLATION})

    async def _trade(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Sets the cookie for the key in the link and opens the app, without the key in the address."""
        given = parse_qs(scope["query_string"].decode("latin-1")).get(KEY_PARAMETER, [""])[0]
        if not self._matches(given):
            await PlainTextResponse(MISSING_KEY_MESSAGE, status_code=403)(scope, receive, send)
            return
        response = RedirectResponse(f"{self._frontend()}/", status_code=303)
        response.set_cookie(COOKIE_NAME, given, max_age=COOKIE_MAX_AGE_SECONDS, path="/", httponly=True, samesite="lax")
        await response(scope, receive, send)

    @staticmethod
    def _cookie(scope: Scope) -> str:
        header = dict(scope["headers"]).get(b"cookie", b"").decode("latin-1")
        try:
            morsel = SimpleCookie(header).get(COOKIE_NAME)
        except CookieError:
            return ""
        return morsel.value if morsel else ""

    def _matches(self, given: str) -> bool:
        return bool(given) and hmac.compare_digest(given.encode(), self._key().encode())

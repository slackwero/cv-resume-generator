"""Every request to the backend carries the app's key, which only its owner can read.

LocalOnlyMiddleware refuses other computers and other websites, but any program on this
computer reached the backend: another account on a shared computer could open the
websocket and read the profile. As in Jupyter, the key comes in a link the app prints when
it starts, and the browser trades it for a cookie.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from cv_generator.app.access_key import (
    ACCESS_PATH,
    COOKIE_NAME,
    KEY_FILE_NAME,
    AccessKeyMiddleware,
    access_link,
    load_or_create_key,
)

KEY = "the-key-of-this-computer"
FRONTEND = "http://127.0.0.1:3000"
WEBSOCKET_HEADERS = {"host": "127.0.0.1:8000", "origin": FRONTEND}


async def _ok(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def _socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("ok")
    await websocket.close()


@pytest.fixture
def client() -> TestClient:
    inner = Starlette(
        routes=[
            Route("/", _ok),
            Route("/ping", _ok),
            Route("/_upload", _ok, methods=["POST"]),
            WebSocketRoute("/_event", _socket),
        ]
    )
    return TestClient(
        AccessKeyMiddleware(inner, key=lambda: KEY, frontend=lambda: FRONTEND), base_url="http://127.0.0.1:8000"
    )


def test_a_request_without_the_key_is_refused_and_told_where_it_is(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 403
    assert KEY_FILE_NAME in response.text
    assert KEY not in response.text


def test_a_websocket_without_the_key_is_refused(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/_event", headers=WEBSOCKET_HEADERS):
            pass

    assert refused.value.code == 1008


def test_the_key_cookie_lets_every_request_through(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, KEY)

    assert client.get("/").status_code == 200
    assert client.post("/_upload", content=b"PK").status_code == 200
    with client.websocket_connect("/_event", headers=WEBSOCKET_HEADERS) as ws:
        assert ws.receive_text() == "ok"


def test_a_wrong_key_is_refused(client: TestClient) -> None:
    client.cookies.set(COOKIE_NAME, KEY + "x")

    assert client.get("/").status_code == 403


def test_the_access_link_trades_the_key_for_a_cookie_and_opens_the_app(client: TestClient) -> None:
    response = client.get(f"{ACCESS_PATH}?key={KEY}", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"{FRONTEND}/"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}={KEY};")
    # Out of reach of the page's scripts, and of any other page on 127.0.0.1: cookies do
    # not tell ports apart. Lax, so a link from another site still opens the app.
    for attribute in ("httponly", "samesite=lax", "path=/", "max-age="):
        assert attribute in cookie.lower()


def test_a_wrong_access_link_sets_nothing(client: TestClient) -> None:
    response = client.get(f"{ACCESS_PATH}?key=guess", follow_redirects=False)

    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_the_health_check_needs_no_key(client: TestClient) -> None:
    """The launcher and the smoke test poll it before anyone has the key; it says nothing."""
    assert client.get("/ping").status_code == 200


def test_the_key_is_created_once_readable_only_by_its_owner(tmp_path: Path) -> None:
    key = load_or_create_key(tmp_path)

    assert len(key) >= 40
    assert load_or_create_key(tmp_path) == key
    if os.name != "nt":
        assert stat.S_IMODE((tmp_path / KEY_FILE_NAME).stat().st_mode) == 0o600


def test_the_link_opens_the_backend_on_127_0_0_1() -> None:
    assert access_link(8000, KEY) == f"http://127.0.0.1:8000{ACCESS_PATH}?key={KEY}"


def test_the_backend_asks_for_the_key_inside_the_local_only_rules() -> None:
    """Outside the upload limit, so a request without the key is not even counted."""
    from cv_generator.app.app import app
    from cv_generator.app.local_only import LocalOnlyMiddleware
    from cv_generator.app.upload_limit import UploadLimitMiddleware

    assert app.api_transformer == [UploadLimitMiddleware, AccessKeyMiddleware, LocalOnlyMiddleware]


def test_the_page_keeps_one_name_and_sends_the_key_with_uploads() -> None:
    """The cookie belongs to 127.0.0.1: a page typed as localhost moves there. In development
    the page (Vite, port 3000) uploads to the backend's port, and the browser only sends a
    cookie to another port when the request asks for it."""
    from cv_generator.app.app import app

    scripts = " ".join(str(component) for component in app.head_components)

    assert "location.hostname === 'localhost'" in scripts
    assert "withCredentials = true" in scripts


@pytest.mark.parametrize("name", [KEY_FILE_NAME, f".{KEY_FILE_NAME}.x1y2z3"])
def test_the_key_never_reaches_git(name: str) -> None:
    """Neither the key nor the temporary file it is written through."""
    root = Path(__file__).parent.parent
    try:
        result = subprocess.run(  # noqa: S603 - a fixed argument list
            ["git", "check-ignore", "-q", f"data/{name}"],  # noqa: S607 - git from the PATH
            cwd=root,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("git is not installed")
    if result.returncode == 128:  # not a git work tree: the launcher's ZIP
        pytest.skip("not a git work tree")

    assert result.returncode == 0, f"data/{name} is not ignored by git"

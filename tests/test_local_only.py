from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.types import Lifespan
from starlette.websockets import WebSocket, WebSocketDisconnect

from cv_generator.app.local_only import LocalOnlyMiddleware, is_allowed_fetch_site, is_allowed_origin, is_local_host


@pytest.mark.parametrize("host", ["localhost", "localhost:8000", "127.0.0.1:3000", "LocalHost:8000"])
def test_local_hosts_are_accepted(host: str) -> None:
    assert is_local_host(host)


@pytest.mark.parametrize(
    "host",
    [None, "", "evil.example", "evil.example:8000", "localhost.evil.example", "127.0.0.1.nip.io:8000", "[::1]:8000"],
)
def test_other_hosts_are_refused(host: str | None) -> None:
    assert not is_local_host(host)


def test_a_request_without_origin_is_allowed() -> None:
    assert is_allowed_origin(None, {3000, 8000})


@pytest.mark.parametrize(
    "origin", ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://LOCALHOST:3000"]
)
def test_the_app_own_origins_are_allowed(origin: str) -> None:
    assert is_allowed_origin(origin, {3000, 8000})


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example",
        "http://localhost:4000",  # a local page, but not this app
        "http://localhost",  # no port: 80 is not the app
        "https://localhost:3000",  # the app is served over http
        "null",  # sandboxed iframes and file:// pages
        "http://localhost:3000.evil.example",  # malformed port: refuse, never raise
        "",
    ],
)
def test_foreign_origins_are_refused(origin: str) -> None:
    assert not is_allowed_origin(origin, {3000, 8000})


@pytest.mark.parametrize("fetch_site", [None, "same-origin", "same-site", "none"])
def test_fetch_sites_other_than_cross_site_are_allowed(fetch_site: str | None) -> None:
    assert is_allowed_fetch_site(fetch_site)


@pytest.mark.parametrize("fetch_site", ["cross-site", "CROSS-SITE"])
def test_a_cross_site_fetch_is_refused(fetch_site: str) -> None:
    assert not is_allowed_fetch_site(fetch_site)


async def _home(_request: object) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def _socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("ok")
    await websocket.close()


def _inner_app(lifespan: Lifespan[Starlette] | None = None) -> Starlette:
    return Starlette(routes=[Route("/", _home), WebSocketRoute("/ws", _socket)], lifespan=lifespan)


@pytest.fixture
def client() -> TestClient:
    wrapped = LocalOnlyMiddleware(_inner_app(), ports=lambda: {3000, 8000})
    return TestClient(wrapped, base_url="http://localhost:8000")


def test_a_request_from_the_app_passes(client: TestClient) -> None:
    assert client.get("/", headers={"origin": "http://localhost:3000"}).status_code == 200


def test_a_request_without_origin_passes(client: TestClient) -> None:
    assert client.get("/").status_code == 200


def test_a_cross_site_request_without_origin_is_refused(client: TestClient) -> None:
    response = client.get("/", headers={"sec-fetch-site": "cross-site"})
    assert response.status_code == 403
    assert response.text == "CV Generator only accepts connections from this computer."


def test_a_same_site_request_without_origin_passes(client: TestClient) -> None:
    assert client.get("/", headers={"sec-fetch-site": "same-site"}).status_code == 200


def test_the_origin_decides_over_the_fetch_site(client: TestClient) -> None:
    headers = {"origin": "http://localhost:3000", "sec-fetch-site": "cross-site"}
    assert client.get("/", headers=headers).status_code == 200


def test_a_foreign_host_is_refused(client: TestClient) -> None:
    response = client.get("/", headers={"host": "evil.example:8000"})
    assert response.status_code == 403
    assert response.text == "CV Generator only accepts connections from this computer."


def test_a_foreign_origin_is_refused(client: TestClient) -> None:
    assert client.get("/", headers={"origin": "http://evil.example"}).status_code == 403


def test_a_malformed_origin_is_refused_not_crashed(client: TestClient) -> None:
    assert client.get("/", headers={"origin": "http://localhost:3000.evil.example"}).status_code == 403


# TestClient ignores its base_url for websockets and sends `Host: testserver`, so the
# websocket tests set the host the browser would send.
APP_WEBSOCKET_HEADERS = {"host": "localhost:8000", "origin": "http://localhost:3000"}


def test_the_websocket_from_the_app_connects(client: TestClient) -> None:
    with client.websocket_connect("/ws", headers=APP_WEBSOCKET_HEADERS) as ws:
        assert ws.receive_text() == "ok"


def test_the_websocket_from_a_foreign_origin_is_refused(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/ws", headers={**APP_WEBSOCKET_HEADERS, "origin": "http://evil.example"}):
            pass
    assert refused.value.code == 1008


def test_lifespan_reaches_the_app() -> None:
    started: list[bool] = []

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        started.append(True)
        yield

    app = _inner_app(lifespan)

    with TestClient(LocalOnlyMiddleware(app, ports=lambda: {3000, 8000})):
        assert started

"""An upload larger than any export is refused while it arrives, not after it is stored.

Reflex hands an upload to its handler only once Starlette has spooled the whole body to a
temporary file, so the handler's own limit came too late to keep a huge request off the
disk.
"""

from collections.abc import Iterator

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from cv_generator.app.upload_limit import UploadLimitMiddleware

LIMIT = 10


async def _count(request: Request) -> PlainTextResponse:
    return PlainTextResponse(str(len(await request.body())))


@pytest.fixture
def client() -> TestClient:
    inner = Starlette(routes=[Route("/_upload", _count, methods=["POST"]), Route("/other", _count, methods=["POST"])])
    return TestClient(UploadLimitMiddleware(inner, limit=LIMIT))


def _chunks(total: int) -> Iterator[bytes]:
    """A body with no Content-Length: it arrives in pieces, as a crafted client can send it."""
    for _ in range(total):
        yield b"x"


def test_an_upload_within_the_limit_goes_through(client: TestClient) -> None:
    response = client.post("/_upload", content=b"x" * LIMIT)

    assert response.status_code == 200
    assert response.text == str(LIMIT)


def test_an_upload_that_declares_more_is_refused_unread(client: TestClient) -> None:
    response = client.post("/_upload", content=b"x" * (LIMIT + 1))

    assert response.status_code == 413
    assert "larger than any LinkedIn export" in response.text


def test_an_upload_without_a_declared_size_is_cut_when_it_passes_the_limit(client: TestClient) -> None:
    response = client.post("/_upload", content=_chunks(LIMIT + 1))

    assert response.status_code == 413


def test_other_requests_are_not_limited(client: TestClient) -> None:
    assert client.post("/other", content=b"x" * (LIMIT + 1)).status_code == 200

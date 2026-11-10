"""Refuses an upload larger than any LinkedIn export while it arrives.

Reflex hands an upload to its handler only once Starlette has spooled the whole request
body to a temporary file, so the handler's own limit came too late: a request of gigabytes
filled the disk first. This counts the body as it comes in and answers 413 past the limit,
whether the request declared its size or not.

The upload box refuses such a file in the browser already, with a message; this is for any
other client.
"""

from starlette.requests import ClientDisconnect
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cv_generator.app.config import MAX_UPLOAD_BYTES, MEGABYTE

UPLOAD_PATH = "/_upload"
# The handler's limit plus room for the multipart envelope: boundaries, part headers and
# the event's arguments.
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + MEGABYTE
TOO_LARGE_MESSAGE = "That file is larger than any LinkedIn export."


class UploadLimitMiddleware:
    """Cuts the body of `POST /_upload` past `limit` bytes."""

    def __init__(self, app: ASGIApp, limit: int = MAX_BODY_BYTES) -> None:
        self._app = app
        self._limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"].rstrip("/") != UPLOAD_PATH:
            await self._app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self._limit:
            await self._refuse(scope, receive, send)
            return

        received = 0
        too_large = False
        started = False

        async def counted() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._limit:
                    # To the app the client left: it stops reading and stores nothing more.
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded(message: Message) -> None:
            nonlocal started
            if too_large:
                return
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self._app(scope, counted, guarded)
        except ClientDisconnect:
            # Reflex catches it and answers; another app may let it out. Only ours is expected.
            if not too_large:
                raise
        if too_large and not started:
            await self._refuse(scope, receive, send)

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse(TOO_LARGE_MESSAGE, status_code=413)(scope, receive, send)

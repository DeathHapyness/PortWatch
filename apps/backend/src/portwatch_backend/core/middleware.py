"""HTTP middleware hooks reserved for request-scoped observability."""

import re
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from starlette.responses import Response

from portwatch_backend.core.logging import bind_request_id, reset_request_id

MAX_REQUEST_ID_LENGTH = 128
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", re.ASCII)


def _safe_request_id(candidate: str | None) -> str:
    """Keep a small log/header-safe client ID or generate a server UUID.

    Request IDs are opaque correlation values, not user content. Restricting
    them to visible ASCII avoids control-character/header injection and keeps
    attacker-controlled log volume bounded. Invalid values are replaced rather
    than rejected so observability metadata can never make a valid API request
    fail.
    """

    if (
        candidate is not None
        and len(candidate) <= MAX_REQUEST_ID_LENGTH
        and _REQUEST_ID_PATTERN.fullmatch(candidate) is not None
    ):
        return candidate
    return str(uuid4())


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = _safe_request_id(request.headers.get("X-Request-Id"))
    request.state.request_id = request_id
    request_id_token = bind_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        reset_request_id(request_id_token)
    response.headers["X-Request-Id"] = request_id
    return response

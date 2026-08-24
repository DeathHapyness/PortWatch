"""HTTP middleware hooks reserved for request-scoped observability."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from starlette.responses import Response


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-Id", "").strip() or str(uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response

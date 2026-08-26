"""Browser-facing security headers applied to every HTTP response."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response


async def security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Disable MIME sniffing and framing for API and documentation responses."""

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

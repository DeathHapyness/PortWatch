"""Cache policy for authenticated monitoring responses."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

_API_PREFIX = "/api/v1"
_METRICS_PATH = "/metrics"


def _contains_sensitive_monitoring_data(path: str) -> bool:
    return path in (_API_PREFIX, _METRICS_PATH) or path.startswith(f"{_API_PREFIX}/")


async def sensitive_response_cache_control_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Prevent storage of API/metrics responses by browsers and proxies.

    Apply the policy after the downstream handler returns so it also covers
    authentication, validation and not-found responses under the protected
    namespace. Health probes and public OpenAPI documentation are intentionally
    unaffected.
    """

    response = await call_next(request)
    if _contains_sensitive_monitoring_data(request.url.path):
        response.headers["Cache-Control"] = "no-store"
    return response

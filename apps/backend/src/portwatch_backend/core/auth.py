"""Static bearer token authentication — per ADR-0004.

A single dependency, applied per-router in app.py to every /api/v1/* route.
health.py's liveness/readiness routes are deliberately NOT protected (S-01:
monitoring probes must not depend on auth being configured correctly to
answer "is the process alive").

When Settings.api_token is empty, auth is a no-op — that's only reachable at
all when bound to loopback, since config.validate_bind_security() refuses to
start otherwise.
"""

import secrets

from fastapi import Header, HTTPException, status

from portwatch_backend.core.config import get_settings

_BEARER_PREFIX = "Bearer "


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_token:
        return

    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = authorization.removeprefix(_BEARER_PREFIX)
    # Constant-time comparison — a naive `==` would let an attacker recover
    # the token byte-by-byte via response-timing differences.
    if not secrets.compare_digest(provided, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

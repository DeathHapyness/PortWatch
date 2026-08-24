"""Liveness/readiness — the only endpoints in this module that are fully real
in Phase 2. Readiness will start checking real dependencies (docker-socket-
proxy, netprobe) once they exist, from Phase 3 onward."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def health_ready() -> dict[str, str]:
    # TODO(Phase 3): check docker-socket-proxy and netprobe connectivity.
    return {"status": "ok"}

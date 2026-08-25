"""Liveness/readiness.

/health is a pure liveness probe — no dependency checks, just "is the
process alive" — and stays that way forever; it must never depend on
Docker being reachable (see architecture blueprint, section 08/S-01).

/health/ready reflects whether the Collector has a usable snapshot: never
collected yet, or stale (its poll cycles have been failing — most likely
docker-socket-proxy is unreachable) both mean "not ready".
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response, status

router = APIRouter(tags=["health"])

# How many missed poll cycles we tolerate before calling the API "not
# ready". One cycle can legitimately fail transiently (e.g. socket-proxy
# restarting) — a small multiplier absorbs that without flapping readiness
# on every brief hiccup, while still catching a Collector that is genuinely
# stuck.
_STALE_CYCLE_TOLERANCE = 3


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def health_ready(request: Request, response: Response) -> dict[str, object]:
    snapshot = request.app.state.snapshot_store.read()

    if snapshot.generation == 0:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "collector has not completed a first collection cycle yet",
        }

    settings = request.app.state.settings
    max_age = timedelta(seconds=settings.collector_poll_interval_seconds * _STALE_CYCLE_TOLERANCE)
    if snapshot.is_stale(now=datetime.now(UTC), max_age=max_age):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "collector snapshot is stale — docker-socket-proxy may be unreachable",
            "generation": snapshot.generation,
            "collected_at": snapshot.collected_at.isoformat(),
        }

    return {
        "status": "ok",
        "generation": snapshot.generation,
        "collected_at": snapshot.collected_at.isoformat(),
        "host_ports_enabled": snapshot.host_ports_enabled,
    }

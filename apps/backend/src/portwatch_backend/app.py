"""FastAPI application factory.

Tracing stays out of the MVP (OpenTelemetry, see CLAUDE.md), and this
middleware stack is the extension point for it later. Structured JSON logs
and Prometheus metrics (Phase 9) are wired up below. Routing, CORS, and RFC 7807-shaped error
responses are the Phase 2 foundation; the Collector lifecycle below is
Phase 3 (see collector/service.py).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from portwatch_backend.api import containers, events, health, networks, ports, system
from portwatch_backend.collector.service import Collector
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.auth import require_api_token
from portwatch_backend.core.cache_control import sensitive_response_cache_control_middleware
from portwatch_backend.core.config import get_settings
from portwatch_backend.core.events import SnapshotBroadcaster
from portwatch_backend.core.logging import configure_logging
from portwatch_backend.core.metrics import PortWatchMetrics, build_http_metrics_middleware
from portwatch_backend.core.middleware import request_id_middleware
from portwatch_backend.core.schemas import ProblemDetail
from portwatch_backend.core.security_headers import security_headers_middleware


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The Collector runs docker-py (sync) in its own dedicated thread — see
    # collector/service.py for why. start()/stop() only manage that thread;
    # they don't block the event loop.
    app.state.collector.start()
    try:
        yield
    finally:
        app.state.collector.stop()
        app.state.event_broadcaster.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    event_broadcaster = SnapshotBroadcaster(
        max_subscribers=settings.websocket_max_subscribers,
    )
    snapshot_store = SnapshotStore(on_publish=event_broadcaster.publish)
    metrics = PortWatchMetrics()
    collector = Collector(settings, snapshot_store, metrics=metrics)

    app = FastAPI(
        title="PortWatch API",
        description="Homelab Docker / container / port monitoring.",
        version="0.1.0",
        lifespan=_lifespan,
    )
    # Available to routes via request.app.state.* (e.g. Phase 4 wiring the
    # stub endpoints in api/*.py to real data, and /health/ready checking
    # snapshot_store.read().is_stale(...)).
    app.state.settings = settings
    app.state.snapshot_store = snapshot_store
    app.state.collector = collector
    app.state.event_broadcaster = event_broadcaster
    app.state.metrics = metrics

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )
    app.middleware("http")(request_id_middleware)
    app.middleware("http")(build_http_metrics_middleware(metrics))
    app.middleware("http")(sensitive_response_cache_control_middleware)
    app.middleware("http")(security_headers_middleware)

    @app.exception_handler(HTTPException)
    async def problem_detail_handler(request: Request, exc: HTTPException) -> JSONResponse:
        title = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        problem = ProblemDetail(
            title=title,
            status=exc.status_code,
            detail=exc.detail,
            request_id=request.state.request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(problem),
            media_type="application/problem+json",
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_problem_detail_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        problem = ProblemDetail(
            title="Request validation error",
            status=422,
            detail=exc.errors(),
            request_id=request.state.request_id,
        )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(problem),
            media_type="application/problem+json",
        )

    # health.router is deliberately excluded — liveness/readiness must stay
    # reachable without a token (S-01). Everything under /api/v1/* requires
    # the bearer token per ADR-0004 (a no-op when api_token is empty, which
    # is only reachable on loopback — see config.validate_bind_security()).
    protected = [Depends(require_api_token)]

    # Register the upgrade route directly. Authentication reads the handshake
    # header inside the endpoint because HTTP Header dependencies do not apply
    # to a WebSocket connection.
    @app.websocket("/api/v1/events", name="snapshot-events")
    async def snapshot_events(websocket: WebSocket) -> None:
        await events.snapshot_events(websocket)

    @app.get(
        "/metrics",
        dependencies=protected,
        summary="Prometheus metrics",
        include_in_schema=False,
    )
    async def prometheus_metrics() -> Response:
        # Bearer-protected like the rest of the API (unlike /health*, which
        # is deliberately open for liveness/readiness probes — see S-01):
        # metrics aren't a liveness signal an orchestrator needs unauthenticated,
        # and Prometheus scrape configs support a static bearer_token natively.
        return Response(
            content=generate_latest(metrics.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    app.include_router(health.router)
    app.include_router(system.router, dependencies=protected)
    app.include_router(containers.router, dependencies=protected)
    app.include_router(networks.router, dependencies=protected)
    app.include_router(ports.router, dependencies=protected)

    return app


app = create_app()

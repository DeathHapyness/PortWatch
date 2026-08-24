"""FastAPI application factory.

Structured logging / metrics / tracing are intentionally not wired up here —
that's Phase 9 (Observability). Routing, CORS, and RFC 7807-shaped error
responses are the Phase 2 foundation; the Collector lifecycle below is
Phase 3 (see collector/service.py).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from portwatch_backend.api import containers, health, networks, ports, system
from portwatch_backend.collector.service import Collector
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.config import get_settings
from portwatch_backend.core.schemas import ProblemDetail


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


def create_app() -> FastAPI:
    settings = get_settings()
    snapshot_store = SnapshotStore()
    collector = Collector(settings, snapshot_store)

    app = FastAPI(
        title="PortWatch API",
        description="Homelab Docker / container / port monitoring.",
        version="0.1.0",
        lifespan=_lifespan,
    )
    # Available to routes via request.app.state.* (e.g. Phase 4 wiring the
    # stub endpoints in api/*.py to real data, and /health/ready checking
    # snapshot_store.read().is_stale(...)).
    app.state.snapshot_store = snapshot_store
    app.state.collector = collector

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def problem_detail_handler(request: Request, exc: HTTPException) -> JSONResponse:
        problem = ProblemDetail(title=exc.detail, status=exc.status_code, detail=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    app.include_router(health.router)
    app.include_router(system.router)
    app.include_router(containers.router)
    app.include_router(networks.router)
    app.include_router(ports.router)

    return app


app = create_app()

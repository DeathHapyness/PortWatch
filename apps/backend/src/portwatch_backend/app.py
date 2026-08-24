"""FastAPI application factory.

Structured logging / metrics / tracing are intentionally not wired up here —
that's Phase 9 (Observability). This is the Phase 2 foundation: routing,
CORS, and RFC 7807-shaped error responses only.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from portwatch_backend.api import containers, health, networks, ports, system
from portwatch_backend.core.config import get_settings
from portwatch_backend.core.schemas import ProblemDetail


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PortWatch API",
        description="Homelab Docker / container / port monitoring.",
        version="0.1.0",
    )

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

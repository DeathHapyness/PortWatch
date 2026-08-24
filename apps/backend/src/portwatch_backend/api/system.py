"""System summary — STUB. Returns static example data shaped exactly like the
real contract so the frontend can build against it. Real data lands in
Phase 4 once the Collector (Phase 3) is feeding state."""

from fastapi import APIRouter

from portwatch_backend.core.schemas import SystemSummary

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/summary", summary="Dashboard-level system summary")
async def get_summary() -> SystemSummary:
    return SystemSummary(
        docker_version="29.6.2",
        docker_api_version="1.51",
        containers_running=0,
        containers_stopped=0,
        networks_total=0,
        ports_used_total=0,
        ports_free_sample=0,
        host_ports_enabled=False,
        collector_last_poll=None,
    )

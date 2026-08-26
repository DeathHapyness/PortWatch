"""System summary — real data from the Collector's snapshot.

`api/ports.py` is deliberately left untouched by this same wiring pass —
it's mid-flight in another task (range/limit validation), and building on
top of it here would collide with that work landing.
"""

from fastapi import APIRouter, Request

from portwatch_backend.core.schemas import SystemSummary

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/summary", summary="Dashboard-level system summary")
async def get_summary(request: Request) -> SystemSummary:
    overview = request.app.state.snapshot_store.read_overview()

    return SystemSummary(
        docker_version=overview.docker_version,
        docker_api_version=overview.docker_api_version,
        containers_running=overview.containers_running,
        containers_stopped=overview.containers_total - overview.containers_running,
        networks_total=overview.networks_total,
        # The snapshot never contains "free" entries by construction (see
        # collector/parsing.build_port_entries) — it's only host/published,
        # so its length is exactly "ports in use", no filtering needed.
        ports_used_total=overview.ports_used_total,
        # Free-port sampling would mean scanning the full configured range
        # on every dashboard poll; the Ports screen computes that on demand
        # with an explicit limit instead (api/ports.py's /available).
        ports_free_sample=0,
        host_ports_enabled=overview.host_ports_enabled,
        collector_last_poll=overview.collected_at if overview.generation > 0 else None,
    )

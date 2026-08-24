"""System summary — real data from the Collector's snapshot.

`api/ports.py` is deliberately left untouched by this same wiring pass —
it's mid-flight in another task (range/limit validation), and building on
top of it here would collide with that work landing.
"""

from fastapi import APIRouter, Request

from portwatch_backend.core.schemas import ContainerStatus, SystemSummary

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/summary", summary="Dashboard-level system summary")
async def get_summary(request: Request) -> SystemSummary:
    snapshot = request.app.state.snapshot_store.read()

    running = sum(1 for c in snapshot.containers if c.status == ContainerStatus.running)

    return SystemSummary(
        docker_version=snapshot.docker_version,
        docker_api_version=snapshot.docker_api_version,
        containers_running=running,
        containers_stopped=len(snapshot.containers) - running,
        networks_total=len(snapshot.networks),
        # snapshot.ports never contains "free" entries by construction (see
        # collector/parsing.build_port_entries) — it's only host/published,
        # so its length is exactly "ports in use", no filtering needed.
        ports_used_total=len(snapshot.ports),
        # Free-port sampling would mean scanning the full configured range
        # on every dashboard poll; the Ports screen computes that on demand
        # with an explicit limit instead (api/ports.py's /available).
        ports_free_sample=0,
        host_ports_enabled=snapshot.host_ports_enabled,
        collector_last_poll=snapshot.collected_at if snapshot.generation > 0 else None,
    )

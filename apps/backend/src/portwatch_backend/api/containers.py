"""Containers — real data from the Collector's snapshot (Phase 3/4).

The snapshot already stores full ContainerDetail objects (see
collector/parsing.parse_container_detail and collector/state.py), so this
module just reads, filters and returns them — no promotion step needed.
labels are redacted by key (PW-03) and env_redacted carries KEYS only,
both already applied by the Collector before publish(); this API layer
never sees raw env values.
"""

from fastapi import APIRouter, HTTPException, Request, status

from portwatch_backend.core.schemas import ContainerDetail, ContainerStatus

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


def _matches_label(summary: ContainerDetail, label: str) -> bool:
    # "key=value" for an exact match, or a bare "key" for presence-only —
    # the contract doesn't pin down a format beyond the single `label`
    # query param, so this is a documented interpretation, not a guess
    # baked in silently.
    key, sep, value = label.partition("=")
    if sep:
        return summary.labels.get(key) == value
    return key in summary.labels


@router.get("", summary="List containers")
async def list_containers(
    request: Request,
    status_filter: ContainerStatus | None = None,
    network: str | None = None,
    label: str | None = None,
    q: str | None = None,
) -> list[ContainerDetail]:
    containers: tuple[ContainerDetail, ...] = request.app.state.snapshot_store.read().containers

    if status_filter is not None:
        containers = tuple(c for c in containers if c.status == status_filter)
    if network is not None:
        containers = tuple(c for c in containers if network in c.networks)
    if label is not None:
        containers = tuple(c for c in containers if _matches_label(c, label))
    if q is not None:
        needle = q.lower()
        containers = tuple(
            c for c in containers if needle in c.name.lower() or needle in c.image.lower()
        )

    return list(containers)


@router.get("/{container_id}", summary="Container detail")
async def get_container(request: Request, container_id: str) -> ContainerDetail:
    container = request.app.state.snapshot_store.find_container(container_id)
    if container is not None:
        return container
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="container not found")

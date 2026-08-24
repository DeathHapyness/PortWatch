"""Containers — real data from the Collector's snapshot (Phase 3/4).

command/env_redacted/mounts are not yet populated: the Collector's parser
(collector/parsing.parse_container_summary) only extracts the summary-level
fields the snapshot stores (see collector/state.py — CollectorSnapshot only
carries ContainerSummary, not a richer detail type). They default to empty
rather than being fabricated — a future increment that extends the snapshot
with detail-level data would fill them in for real.
"""

from fastapi import APIRouter, HTTPException, Request, status

from portwatch_backend.core.schemas import ContainerDetail, ContainerStatus, ContainerSummary

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


def _to_detail(summary: ContainerSummary) -> ContainerDetail:
    return ContainerDetail(**summary.model_dump())


def _matches_label(summary: ContainerSummary, label: str) -> bool:
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
    containers = request.app.state.snapshot_store.read().containers

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

    return [_to_detail(c) for c in containers]


@router.get("/{container_id}", summary="Container detail")
async def get_container(request: Request, container_id: str) -> ContainerDetail:
    containers = request.app.state.snapshot_store.read().containers
    for container in containers:
        if container_id in (container.id, container.name):
            return _to_detail(container)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="container not found")

"""Containers — STUB, see api/system.py docstring. Real implementation reads
from the Collector's in-memory state (Phase 3/4)."""

from fastapi import APIRouter, HTTPException, status

from portwatch_backend.core.schemas import ContainerDetail, ContainerStatus

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])

_EXAMPLE = ContainerDetail(
    id="a1b2c3d4e5f6",
    name="portwatch-dev-fixture-web",
    image="nginx:alpine",
    status=ContainerStatus.running,
    health=None,
    created_at="2026-08-23T22:00:00Z",
    networks=["portwatch-dev-net"],
    ports=[],
    labels={"portwatch.env": "dev-sandbox"},
    command="nginx -g daemon off;",
    env_redacted=["NGINX_VERSION"],
    mounts=[],
)


@router.get("", summary="List containers")
async def list_containers(
    status_filter: ContainerStatus | None = None,
    network: str | None = None,
    label: str | None = None,
    q: str | None = None,
) -> list[ContainerDetail]:
    return [_EXAMPLE]


@router.get("/{container_id}", summary="Container detail")
async def get_container(container_id: str) -> ContainerDetail:
    if container_id != _EXAMPLE.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="container not found")
    return _EXAMPLE

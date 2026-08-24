"""Networks — STUB, see api/system.py docstring."""

from fastapi import APIRouter, HTTPException, status

from portwatch_backend.core.schemas import NetworkDetail

router = APIRouter(prefix="/api/v1/networks", tags=["networks"])

_EXAMPLE = NetworkDetail(
    id="net-0001",
    name="portwatch-dev-net",
    driver="bridge",
    scope="local",
    containers=["portwatch-dev-fixture-web"],
    subnet="172.20.0.0/16",
    gateway="172.20.0.1",
)


@router.get("", summary="List Docker networks")
async def list_networks() -> list[NetworkDetail]:
    return [_EXAMPLE]


@router.get("/{network_id}", summary="Network detail")
async def get_network(network_id: str) -> NetworkDetail:
    if network_id != _EXAMPLE.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    return _EXAMPLE

"""Networks — real data from the Collector's snapshot.

subnet/gateway are not yet populated: collector/parsing.parse_network_summary
only extracts the summary-level fields the snapshot stores (see
collector/state.py — CollectorSnapshot only carries NetworkSummary). They
default to None rather than being fabricated, same reasoning as
api/containers.py's ContainerDetail promotion.
"""

from fastapi import APIRouter, HTTPException, Request, status

from portwatch_backend.core.schemas import NetworkDetail, NetworkSummary

router = APIRouter(prefix="/api/v1/networks", tags=["networks"])


def _to_detail(summary: NetworkSummary) -> NetworkDetail:
    return NetworkDetail(**summary.model_dump())


@router.get("", summary="List Docker networks")
async def list_networks(request: Request) -> list[NetworkDetail]:
    networks = request.app.state.snapshot_store.read().networks
    return [_to_detail(n) for n in networks]


@router.get("/{network_id}", summary="Network detail")
async def get_network(request: Request, network_id: str) -> NetworkDetail:
    networks = request.app.state.snapshot_store.read().networks
    for network in networks:
        if network_id in (network.id, network.name):
            return _to_detail(network)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")

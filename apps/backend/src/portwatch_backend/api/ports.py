"""Unified port view backed by the Collector's latest coherent snapshot."""

from fastapi import APIRouter, HTTPException, Request, status

from portwatch_backend.core.config import get_settings
from portwatch_backend.core.schemas import PortEntry, PortProtocol, PortsResponse, PortState

router = APIRouter(prefix="/api/v1/ports", tags=["ports"])

MIN_PORT = 0
MAX_PORT = 65535
MAX_AVAILABLE_LIMIT = 1000


def _resolve_range(range_start: int | None, range_end: int | None) -> tuple[int, int]:
    settings = get_settings()
    start = settings.port_range_start if range_start is None else range_start
    end = settings.port_range_end if range_end is None else range_end

    if not MIN_PORT <= start <= MAX_PORT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"range_start must be between {MIN_PORT} and {MAX_PORT}",
        )
    if not MIN_PORT <= end <= MAX_PORT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"range_end must be between {MIN_PORT} and {MAX_PORT}",
        )
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="range_start must be <= range_end",
        )
    return start, end


@router.get("", summary="Unified port view (host / published / free)")
async def list_ports(
    request: Request,
    state: PortState | None = None,
    range_start: int | None = None,
    range_end: int | None = None,
) -> PortsResponse:
    start, end = _resolve_range(range_start, range_end)
    ports = request.app.state.snapshot_store.read_ports()
    entries = [
        entry
        for entry in ports
        if start <= entry.port <= end and (state is None or entry.state == state)
    ]
    return PortsResponse(range_start=start, range_end=end, entries=entries)


@router.get("/available", summary="Free ports within a range")
async def list_available_ports(
    request: Request,
    range_start: int | None = None,
    range_end: int | None = None,
    limit: int = 50,
) -> PortsResponse:
    start, end = _resolve_range(range_start, range_end)
    if not 1 <= limit <= MAX_AVAILABLE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"limit must be between 1 and {MAX_AVAILABLE_LIMIT}",
        )

    ports = request.app.state.snapshot_store.read_ports()
    occupied = {
        entry.port for entry in ports if entry.state in (PortState.host, PortState.published)
    }
    entries: list[PortEntry] = []
    for port in range(start, end + 1):
        if port in occupied:
            continue
        entries.append(
            PortEntry(
                port=port,
                protocol=PortProtocol.tcp,
                state=PortState.free,
                owner=None,
            )
        )
        if len(entries) == limit:
            break

    return PortsResponse(range_start=start, range_end=end, entries=entries)

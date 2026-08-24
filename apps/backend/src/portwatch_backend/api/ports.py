"""Ports — STUB, see api/system.py docstring. Real "host" entries require the
netprobe component (Phase 3); real "published" entries come from the
Collector's container inspection."""

from fastapi import APIRouter, HTTPException, status

from portwatch_backend.core.config import get_settings
from portwatch_backend.core.schemas import PortEntry, PortProtocol, PortsResponse, PortState

router = APIRouter(prefix="/api/v1/ports", tags=["ports"])


@router.get("", summary="Unified port view (host / published / free)")
async def list_ports(
    state: PortState | None = None,
    range_start: int | None = None,
    range_end: int | None = None,
) -> PortsResponse:
    settings = get_settings()
    start = range_start or settings.port_range_start
    end = range_end or settings.port_range_end
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="range_start must be <= range_end"
        )
    example = PortEntry(
        port=8081,
        protocol=PortProtocol.tcp,
        state=PortState.published,
        owner="portwatch-dev-fixture-web",
    )
    entries = [example] if state in (None, PortState.published) else []
    return PortsResponse(range_start=start, range_end=end, entries=entries)


@router.get("/available", summary="Free ports within a range")
async def list_available_ports(
    range_start: int | None = None,
    range_end: int | None = None,
    limit: int = 50,
) -> PortsResponse:
    settings = get_settings()
    start = range_start or settings.port_range_start
    end = range_end or settings.port_range_end
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="range_start must be <= range_end"
        )
    return PortsResponse(range_start=start, range_end=end, entries=[])

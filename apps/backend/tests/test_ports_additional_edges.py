"""Additional endpoint regressions for port boundaries and filtering."""

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from portwatch_backend.app import app
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.schemas import PortEntry, PortProtocol, PortState


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.fixture
def snapshot_store() -> Iterator[SnapshotStore]:
    original = app.state.snapshot_store
    store = SnapshotStore()
    app.state.snapshot_store = store
    try:
        yield store
    finally:
        app.state.snapshot_store = original


def _seed_edges(store: SnapshotStore) -> None:
    store.publish(
        ports=[
            PortEntry(port=0, protocol=PortProtocol.tcp, state=PortState.host),
            PortEntry(port=53, protocol=PortProtocol.tcp, state=PortState.host),
            PortEntry(port=53, protocol=PortProtocol.udp, state=PortState.published, owner="dns"),
            PortEntry(
                port=65535, protocol=PortProtocol.tcp, state=PortState.published, owner="edge"
            ),
        ]
    )


async def test_list_ports_includes_both_valid_port_boundaries(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed_edges(snapshot_store)

    response = await client.get(
        "/api/v1/ports",
        params={"range_start": 0, "range_end": 65535},
    )

    assert response.status_code == 200
    assert [(entry["port"], entry["state"]) for entry in response.json()["entries"]] == [
        (0, "host"),
        (53, "host"),
        (53, "published"),
        (65535, "published"),
    ]


async def test_list_ports_state_filter_keeps_only_matching_entries(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed_edges(snapshot_store)

    response = await client.get(
        "/api/v1/ports",
        params={"state": "host", "range_start": 0, "range_end": 65535},
    )

    assert response.status_code == 200
    assert response.json()["entries"] == [
        {"port": 0, "protocol": "tcp", "state": "host", "owner": None},
        {"port": 53, "protocol": "tcp", "state": "host", "owner": None},
    ]


async def test_available_ports_uses_numeric_occupancy_across_protocols(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed_edges(snapshot_store)

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 52, "range_end": 54, "limit": 10},
    )

    assert response.status_code == 200
    assert [entry["port"] for entry in response.json()["entries"]] == [52, 54]
    assert all(entry["protocol"] == "tcp" for entry in response.json()["entries"])


async def test_available_ports_returns_no_entries_when_every_port_is_occupied(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed_edges(snapshot_store)

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 0, "range_end": 0, "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["entries"] == []

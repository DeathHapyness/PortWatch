"""Port endpoints backed by a throwaway Collector snapshot."""

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


def _seed(store: SnapshotStore) -> None:
    store.publish(
        ports=[
            PortEntry(port=22, protocol=PortProtocol.tcp, state=PortState.host),
            PortEntry(port=53, protocol=PortProtocol.udp, state=PortState.host),
            PortEntry(
                port=8081,
                protocol=PortProtocol.tcp,
                state=PortState.published,
                owner="portwatch-dev-fixture-web",
            ),
            PortEntry(
                port=9000,
                protocol=PortProtocol.udp,
                state=PortState.published,
                owner="portwatch-dev-dns",
            ),
        ]
    )


async def test_list_ports_reflects_snapshot_and_preserves_order(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    response = await client.get("/api/v1/ports", params={"range_start": 0, "range_end": 65535})

    assert response.status_code == 200
    body = response.json()
    assert body["range_start"] == 0
    assert body["range_end"] == 65535
    assert [(entry["port"], entry["state"]) for entry in body["entries"]] == [
        (22, "host"),
        (53, "host"),
        (8081, "published"),
        (9000, "published"),
    ]


async def test_list_ports_filters_by_state_and_inclusive_range(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    response = await client.get(
        "/api/v1/ports",
        params={"state": "published", "range_start": 8081, "range_end": 8081},
    )

    assert response.status_code == 200
    assert response.json()["entries"] == [
        {
            "port": 8081,
            "protocol": "tcp",
            "state": "published",
            "owner": "portwatch-dev-fixture-web",
        }
    ]


async def test_list_ports_free_filter_does_not_fabricate_snapshot_entries(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    response = await client.get("/api/v1/ports", params={"state": "free"})

    assert response.status_code == 200
    assert response.json()["entries"] == []


async def test_available_ports_excludes_host_and_published_numbers_and_honors_limit(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 20, "range_end": 55, "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert [entry["port"] for entry in body["entries"]] == [20, 21, 23, 24, 25]
    assert all(
        (entry["protocol"], entry["state"], entry["owner"]) == ("tcp", "free", None)
        for entry in body["entries"]
    )


async def test_available_ports_accepts_zero_as_an_explicit_boundary(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 0, "range_end": 0, "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["entries"] == [
        {"port": 0, "protocol": "tcp", "state": "free", "owner": None}
    ]


@pytest.mark.parametrize(
    ("range_start", "range_end", "expected"),
    [
        (52, 54, [52, 54]),  # 53/udp is occupied by the host
        (8999, 9001, [8999, 9001]),  # 9000/udp is published by Docker
    ],
)
async def test_available_ports_treats_any_protocol_as_occupied(
    client: httpx.AsyncClient,
    snapshot_store: SnapshotStore,
    range_start: int,
    range_end: int,
    expected: list[int],
) -> None:
    _seed(snapshot_store)

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": range_start, "range_end": range_end, "limit": 10},
    )

    assert response.status_code == 200
    assert [entry["port"] for entry in response.json()["entries"]] == expected


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/v1/ports", {"range_start": -1, "range_end": 10}),
        ("/api/v1/ports", {"range_start": 0, "range_end": 65536}),
        ("/api/v1/ports", {"range_start": 100, "range_end": 99}),
        ("/api/v1/ports/available", {"range_start": -1, "range_end": 10}),
        ("/api/v1/ports/available", {"range_start": 0, "range_end": 65536}),
        ("/api/v1/ports/available", {"range_start": 100, "range_end": 99}),
    ],
)
async def test_endpoints_reject_invalid_ranges_with_400(
    client: httpx.AsyncClient,
    snapshot_store: SnapshotStore,
    path: str,
    params: dict[str, int],
) -> None:
    _seed(snapshot_store)

    response = await client.get(path, params=params)

    assert response.status_code == 400


@pytest.mark.parametrize("limit", [0, -1, 1001])
async def test_available_ports_rejects_invalid_limit_with_400(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore, limit: int
) -> None:
    _seed(snapshot_store)

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 1, "range_end": 10, "limit": limit},
    )

    assert response.status_code == 400

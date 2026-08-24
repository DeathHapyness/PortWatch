"""Golden-file regressions for port/interface/protocol edge cases."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from portwatch_backend.app import app
from portwatch_backend.collector.parsing import build_port_entries
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.schemas import (
    ContainerSummary,
    PortEntry,
    PortProtocol,
    PortState,
    PublishedPort,
)

GOLDEN_FILE = Path(__file__).parents[1] / "fixtures" / "port_edge_cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_FILE.read_text())


def _containers(raw_containers: list[dict[str, Any]]) -> list[ContainerSummary]:
    return [
        ContainerSummary(
            id=container["id"],
            name=container["name"],
            image="fixture:edge-case",
            status="running",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ports=[PublishedPort(**port) for port in container["ports"]],
        )
        for container in raw_containers
    ]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["name"])
def test_build_port_entries_matches_golden_file(case: dict[str, Any]) -> None:
    entries = build_port_entries(_containers(case["containers"]), case["host_ports"])

    assert [entry.model_dump(mode="json") for entry in entries] == case["expected"]


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.fixture
def snapshot_store() -> SnapshotStore:
    original = app.state.snapshot_store
    store = SnapshotStore()
    app.state.snapshot_store = store
    try:
        yield store
    finally:
        app.state.snapshot_store = original


async def test_port_endpoints_expose_golden_edge_case(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    case = _load_cases()[2]
    expected = case["expected"]
    entries = [
        PortEntry(
            port=entry["port"],
            protocol=PortProtocol(entry["protocol"]),
            state=PortState(entry["state"]),
            owner=entry["owner"],
        )
        for entry in expected
    ]
    snapshot_store.publish(ports=entries)

    response = await client.get("/api/v1/ports", params={"range_start": 8081, "range_end": 8081})
    available = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 8081, "range_end": 8082, "limit": 10},
    )

    assert response.status_code == 200
    assert response.json()["entries"] == expected
    assert available.status_code == 200
    assert [entry["port"] for entry in available.json()["entries"]] == [8082]

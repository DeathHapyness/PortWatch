from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from portwatch_backend.app import app
from portwatch_backend.collector.state import SnapshotStore


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def fresh_snapshot_store() -> Iterator[SnapshotStore]:
    """Swap in a throwaway SnapshotStore for one test and restore the real
    one after — `app` is a module-level singleton shared by the whole test
    session (see conftest.py's `client` fixture), so mutating its store
    directly would leak state into unrelated tests depending on run order.
    """

    original = app.state.snapshot_store
    store = SnapshotStore()
    app.state.snapshot_store = store
    try:
        yield store
    finally:
        app.state.snapshot_store = original


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_ready_before_first_collection_cycle(
    client: httpx.AsyncClient, fresh_snapshot_store: SnapshotStore
) -> None:
    # generation 0 — the Collector hasn't published anything yet.
    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"


async def test_health_ready_with_a_fresh_snapshot(
    client: httpx.AsyncClient, fresh_snapshot_store: SnapshotStore
) -> None:
    fresh_snapshot_store.publish(collected_at=datetime.now(UTC))

    resp = await client.get("/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["generation"] == 1


async def test_health_ready_with_a_stale_snapshot(
    client: httpx.AsyncClient, fresh_snapshot_store: SnapshotStore
) -> None:
    # Older than any reasonable poll-interval-based tolerance.
    fresh_snapshot_store.publish(collected_at=datetime.now(UTC) - timedelta(hours=1))

    resp = await client.get("/health/ready")

    assert resp.status_code == 503
    assert resp.json()["status"] == "not_ready"


async def test_system_summary_matches_contract(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/system/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "docker_version" in body
    assert "ports_used_total" in body


async def test_container_not_found_is_problem_json(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/containers/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["status"] == 404

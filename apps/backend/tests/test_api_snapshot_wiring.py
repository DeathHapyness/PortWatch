"""containers/networks/system now read from the Collector's real snapshot
instead of a hardcoded example — these tests publish a known snapshot into
a throwaway store and assert the API reflects it exactly.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest

from portwatch_backend.app import app
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.schemas import (
    ContainerDetail,
    ContainerStatus,
    NetworkSummary,
    PortEntry,
    PortProtocol,
    PortState,
    PublishedPort,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
async def client() -> Iterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def snapshot_store() -> Iterator[SnapshotStore]:
    """Swap in a throwaway SnapshotStore for one test and restore the real
    one after — `app` is a module-level singleton shared by the whole test
    session, so mutating its store directly would leak state into unrelated
    tests depending on run order (see tests/test_health.py for the same
    pattern)."""

    original = app.state.snapshot_store
    store = SnapshotStore()
    app.state.snapshot_store = store
    try:
        yield store
    finally:
        app.state.snapshot_store = original


def _web_container() -> ContainerDetail:
    return ContainerDetail(
        id="abc123def456",
        name="portwatch-dev-fixture-web",
        image="nginx:alpine",
        status=ContainerStatus.running,
        created_at=NOW,
        networks=["portwatch-dev-net"],
        ports=[PublishedPort(container_port=80, host_port=8081, protocol=PortProtocol.tcp)],
        # Already redacted by the Collector before publish() — this fixture
        # mirrors what parse_container_detail would have produced, not raw
        # Docker attrs (see collector/parsing.py for the actual redaction).
        labels={"portwatch.env": "dev-sandbox", "com.example.token": "[redacted]"},
        command="nginx -g daemon off;",
        env_redacted=["NGINX_VERSION", "PATH"],
        mounts=["bind:/etc/nginx/conf.d"],
    )


def _stopped_container() -> ContainerDetail:
    return ContainerDetail(
        id="def456abc789",
        name="portwatch-dev-old-thing",
        image="redis:7",
        status=ContainerStatus.exited,
        created_at=NOW,
        networks=[],
        labels={},
    )


def _seed(store: SnapshotStore) -> None:
    store.publish(
        containers=[_web_container(), _stopped_container()],
        networks=[
            NetworkSummary(
                id="net-0001",
                name="portwatch-dev-net",
                driver="bridge",
                scope="local",
                containers=["portwatch-dev-fixture-web"],
            )
        ],
        ports=[
            PortEntry(
                port=8081,
                protocol=PortProtocol.tcp,
                state=PortState.published,
                owner="portwatch-dev-fixture-web",
            ),
            PortEntry(port=22, protocol=PortProtocol.tcp, state=PortState.host, owner=None),
        ],
        docker_version="29.6.2",
        docker_api_version="1.55",
        host_ports_enabled=True,
        collected_at=NOW,
    )


# --- containers ---------------------------------------------------------------


async def test_list_containers_reflects_the_real_snapshot(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/containers")

    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()}
    assert names == {"portwatch-dev-fixture-web", "portwatch-dev-old-thing"}


async def test_list_containers_filters_by_status(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/containers", params={"status_filter": "running"})

    assert [c["name"] for c in resp.json()] == ["portwatch-dev-fixture-web"]


async def test_list_containers_filters_by_label_key_value(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/containers", params={"label": "portwatch.env=dev-sandbox"})

    assert [c["name"] for c in resp.json()] == ["portwatch-dev-fixture-web"]


async def test_list_containers_filters_by_search_query(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/containers", params={"q": "redis"})

    assert [c["name"] for c in resp.json()] == ["portwatch-dev-old-thing"]


async def test_get_container_by_id_or_name(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    by_id = await client.get("/api/v1/containers/abc123def456")
    by_name = await client.get("/api/v1/containers/portwatch-dev-fixture-web")

    assert by_id.status_code == by_name.status_code == 200
    assert by_id.json()["name"] == by_name.json()["name"] == "portwatch-dev-fixture-web"


async def test_get_container_detail_exposes_command_env_keys_and_mounts(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/containers/portwatch-dev-fixture-web")

    assert resp.status_code == 200
    body = resp.json()
    assert body["command"] == "nginx -g daemon off;"
    assert body["env_redacted"] == ["NGINX_VERSION", "PATH"]
    assert body["mounts"] == ["bind:/etc/nginx/conf.d"]
    # Already-redacted by the Collector — the API must not re-expose or
    # further transform label values, just pass them through.
    assert body["labels"]["com.example.token"] == "[redacted]"


async def test_get_container_not_found_is_problem_json(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/containers/does-not-exist")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


# --- networks ------------------------------------------------------------------


async def test_list_networks_reflects_the_real_snapshot(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/networks")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "portwatch-dev-net"
    assert body[0]["containers"] == ["portwatch-dev-fixture-web"]


async def test_get_network_by_id_or_name(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    by_id = await client.get("/api/v1/networks/net-0001")
    by_name = await client.get("/api/v1/networks/portwatch-dev-net")

    assert by_id.status_code == by_name.status_code == 200
    assert by_id.json()["name"] == by_name.json()["name"] == "portwatch-dev-net"


async def test_get_network_not_found_is_problem_json(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/networks/does-not-exist")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")


# --- system summary --------------------------------------------------------------


async def test_system_summary_reflects_the_real_snapshot(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    _seed(snapshot_store)

    resp = await client.get("/api/v1/system/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["docker_version"] == "29.6.2"
    assert body["containers_running"] == 1
    assert body["containers_stopped"] == 1
    assert body["networks_total"] == 1
    assert body["ports_used_total"] == 2
    assert body["host_ports_enabled"] is True
    assert body["collector_last_poll"] is not None


async def test_system_summary_before_first_collection_has_no_last_poll(
    client: httpx.AsyncClient, snapshot_store: SnapshotStore
) -> None:
    resp = await client.get("/api/v1/system/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["collector_last_poll"] is None
    assert body["containers_running"] == 0

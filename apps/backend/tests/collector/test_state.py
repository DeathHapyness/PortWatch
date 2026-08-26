from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from portwatch_backend.collector.state import CollectorSnapshot, SnapshotStore
from portwatch_backend.core.schemas import (
    ContainerDetail,
    ContainerStatus,
    NetworkSummary,
    PortEntry,
    PortProtocol,
    PortState,
)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def make_container(name: str) -> ContainerDetail:
    return ContainerDetail(
        id=name,
        name=name,
        image="nginx:alpine",
        status=ContainerStatus.running,
        created_at=NOW,
    )


def make_network(name: str) -> NetworkSummary:
    return NetworkSummary(id=name, name=name, driver="bridge", scope="local")


def make_port(port: int, owner: str) -> PortEntry:
    return PortEntry(
        port=port,
        protocol=PortProtocol.tcp,
        state=PortState.published,
        owner=owner,
    )


def test_store_starts_with_an_empty_generation() -> None:
    store = SnapshotStore(clock=lambda: NOW)

    snapshot = store.read()

    assert snapshot == CollectorSnapshot(generation=0, collected_at=NOW)


def test_publish_replaces_the_whole_snapshot_and_increments_generation() -> None:
    store = SnapshotStore(clock=lambda: NOW)

    first = store.publish(containers=[make_container("first")])
    second = store.publish(
        containers=[make_container("second")],
        networks=[make_network("second")],
        ports=[make_port(8080, "second")],
        docker_version="29.0.0",
        docker_api_version="1.51",
        host_ports_enabled=True,
    )

    assert first.generation == 1
    assert second.generation == 2
    assert [container.name for container in second.containers] == ["second"]
    assert [network.name for network in second.networks] == ["second"]
    assert [port.owner for port in second.ports] == ["second"]
    assert second.docker_version == "29.0.0"
    assert second.host_ports_enabled is True


def test_store_detaches_values_from_producers_and_consumers() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    source = make_container("original")

    published = store.publish(containers=[source])
    source.name = "producer-mutated"
    published.containers[0].name = "consumer-mutated"

    assert store.read().containers[0].name == "original"


def test_read_containers_returns_only_containers() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    store.publish(
        containers=[make_container("web")],
        networks=[make_network("dev-net")],
        ports=[make_port(8080, "web")],
    )

    containers = store.read_containers()

    assert [c.name for c in containers] == ["web"]


def test_read_networks_returns_only_networks() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    store.publish(
        containers=[make_container("web")],
        networks=[make_network("dev-net")],
        ports=[make_port(8080, "web")],
    )

    networks = store.read_networks()

    assert [n.name for n in networks] == ["dev-net"]


def test_read_ports_returns_only_ports() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    store.publish(
        containers=[make_container("web")],
        networks=[make_network("dev-net")],
        ports=[make_port(8080, "web")],
    )

    ports = store.read_ports()

    assert [p.owner for p in ports] == ["web"]


def test_read_containers_networks_ports_are_empty_before_any_publish() -> None:
    store = SnapshotStore(clock=lambda: NOW)

    assert store.read_containers() == ()
    assert store.read_networks() == ()
    assert store.read_ports() == ()


def test_read_containers_is_detached_from_producers_and_consumers() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    source = make_container("original")
    store.publish(containers=[source])

    source.name = "producer-mutated"
    read_back = store.read_containers()
    read_back[0].name = "consumer-mutated"

    assert store.read_containers()[0].name == "original"


def test_read_networks_is_detached_from_producers_and_consumers() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    source = make_network("original")
    store.publish(networks=[source])

    source.name = "producer-mutated"
    read_back = store.read_networks()
    read_back[0].name = "consumer-mutated"

    assert store.read_networks()[0].name == "original"


def test_read_ports_is_detached_from_producers_and_consumers() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    source = make_port(8080, "original")
    store.publish(ports=[source])

    source.owner = "producer-mutated"
    read_back = store.read_ports()
    read_back[0].owner = "consumer-mutated"

    assert store.read_ports()[0].owner == "original"


def test_read_containers_networks_ports_reflect_the_latest_generation() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    store.publish(containers=[make_container("first")], networks=[make_network("first")])
    store.publish(containers=[make_container("second")], networks=[make_network("second")])

    assert [c.name for c in store.read_containers()] == ["second"]
    assert [n.name for n in store.read_networks()] == ["second"]


def test_snapshot_staleness_uses_an_explicit_clock() -> None:
    snapshot = CollectorSnapshot(generation=1, collected_at=NOW)

    assert snapshot.is_stale(now=NOW + timedelta(seconds=31), max_age=timedelta(seconds=30))
    assert not snapshot.is_stale(now=NOW + timedelta(seconds=30), max_age=timedelta(seconds=30))


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (
            lambda: CollectorSnapshot(generation=-1, collected_at=NOW),
            "generation must be non-negative",
        ),
        (
            lambda: CollectorSnapshot(generation=0, collected_at=NOW.replace(tzinfo=None)),
            "collected_at must be timezone-aware",
        ),
        (
            lambda: CollectorSnapshot(generation=0, collected_at=NOW).is_stale(
                now=NOW, max_age=timedelta(seconds=-1)
            ),
            "max_age must be non-negative",
        ),
    ],
)
def test_invalid_snapshot_values_are_rejected(
    operation: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        operation()


def test_concurrent_readers_never_observe_a_mixed_generation() -> None:
    store = SnapshotStore(clock=lambda: NOW)
    publication_count = 100

    def publish(index: int) -> None:
        owner = f"generation-{index}"
        store.publish(
            containers=[make_container(owner), make_container(owner)],
            networks=[make_network(owner)],
            ports=[make_port(10_000 + index, owner)],
        )

    def read_repeatedly() -> None:
        for _ in range(publication_count):
            snapshot = store.read()
            if not snapshot.containers:
                continue
            owners = {
                *(container.name for container in snapshot.containers),
                *(network.name for network in snapshot.networks),
                *(port.owner for port in snapshot.ports),
            }
            assert len(owners) == 1

    with ThreadPoolExecutor(max_workers=8) as executor:
        publishers = [executor.submit(publish, index) for index in range(publication_count)]
        readers = [executor.submit(read_repeatedly) for _ in range(4)]
        for future in [*publishers, *readers]:
            future.result()

    assert store.read().generation == publication_count

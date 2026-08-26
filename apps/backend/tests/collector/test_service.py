"""Unit tests for collector/service.py's orchestration logic — a fake
docker-py client is injected via Collector's client_factory, so these never
touch a real daemon or socket-proxy. The real-daemon path is covered
separately by tests/collector/test_integration.py.
"""

import logging
import threading
import time
from typing import Any
from unittest.mock import Mock

import pytest

from portwatch_backend.collector.netprobe_client import NetprobeError
from portwatch_backend.collector.service import CollectionBudgetExceeded, Collector
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.config import Settings


class _FakeContainer:
    def __init__(self, attrs: dict, *, reload_error: Exception | None = None) -> None:
        self.attrs = attrs
        self.id = attrs["Id"]
        self._reload_error = reload_error

    def reload(self) -> None:
        if self._reload_error is not None:
            raise self._reload_error


class _FakeNetwork:
    def __init__(self, attrs: dict) -> None:
        self.attrs = attrs
        self.id = attrs["Id"]

    def reload(self) -> None:
        pass


class _FakeContainerCollection:
    def __init__(self, containers: list[_FakeContainer]) -> None:
        self._containers = containers

    def list(self, all: bool = False) -> list[_FakeContainer]:  # noqa: A002
        return self._containers


class _FakeNetworkCollection:
    def __init__(self, networks: list[_FakeNetwork]) -> None:
        self._networks = networks

    def list(self) -> list[_FakeNetwork]:
        return self._networks


class _FakeDockerClient:
    def __init__(
        self,
        *,
        containers: list[_FakeContainer] | None = None,
        networks: list[_FakeNetwork] | None = None,
        version_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.containers = _FakeContainerCollection(containers or [])
        self.networks = _FakeNetworkCollection(networks or [])
        self._version_error = version_error
        self._close_error = close_error
        self.closed = False

    def version(self) -> dict:
        if self._version_error is not None:
            raise self._version_error
        return {"Version": "29.6.2", "ApiVersion": "1.55"}

    def close(self) -> None:
        self.closed = True
        if self._close_error is not None:
            raise self._close_error


def _container_attrs(name: str, *, status: str = "running") -> dict:
    return {
        "Id": f"{name}-id-0123456789abcdef",
        "Name": f"/{name}",
        "Created": "2026-08-24T00:00:00.000000000Z",
        "State": {"Status": status},
        "Config": {"Image": "nginx:alpine", "Labels": {"portwatch.env": "dev-sandbox"}},
        "NetworkSettings": {"Networks": {"portwatch-dev-net": {}}, "Ports": {}},
    }


def _network_attrs(name: str) -> dict:
    return {
        "Id": f"{name}-id",
        "Name": name,
        "Driver": "bridge",
        "Scope": "local",
        "Containers": {},
    }


# --- collect_once: happy path -------------------------------------------------


def test_collect_once_publishes_a_full_snapshot() -> None:
    fake_client = _FakeDockerClient(
        containers=[_FakeContainer(_container_attrs("fixture-web"))],
        networks=[_FakeNetwork(_network_attrs("portwatch-dev-net"))],
    )
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    snapshot = collector.collect_once()

    assert snapshot.generation == 1
    assert [c.name for c in snapshot.containers] == ["fixture-web"]
    assert [n.name for n in snapshot.networks] == ["portwatch-dev-net"]
    assert snapshot.docker_version == "29.6.2"
    assert snapshot.docker_api_version == "1.55"
    assert snapshot.host_ports_enabled is False
    assert snapshot.warnings == ()
    assert fake_client.closed is True  # collect_once() always closes its client
    assert store.read().generation == 1


def test_collect_once_uses_netprobe_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeDockerClient()
    settings = Settings(netprobe_url="http://127.0.0.1:8088")
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    monkeypatch.setattr(
        "portwatch_backend.collector.service.fetch_host_ports",
        lambda url: [{"protocol": "tcp", "port": 22, "family": "ipv4", "address": "0.0.0.0"}],
    )

    snapshot = collector.collect_once()

    assert snapshot.host_ports_enabled is True
    assert [p.port for p in snapshot.ports] == [22]


# --- error isolation ----------------------------------------------------------


def test_collect_once_skips_one_bad_container_without_failing_the_cycle() -> None:
    good = _FakeContainer(_container_attrs("good"))
    bad = _FakeContainer(_container_attrs("bad"), reload_error=RuntimeError("boom"))
    fake_client = _FakeDockerClient(containers=[good, bad])
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    snapshot = collector.collect_once()

    assert [c.name for c in snapshot.containers] == ["good"]
    assert len(snapshot.warnings) == 1
    assert "bad" in snapshot.warnings[0] or bad.id[:12] in snapshot.warnings[0]


def test_collect_once_degrades_gracefully_when_netprobe_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeDockerClient(containers=[_FakeContainer(_container_attrs("fixture-web"))])
    settings = Settings(netprobe_url="http://127.0.0.1:8088")
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    def _raise(url: str) -> list:
        raise NetprobeError("connection refused")

    monkeypatch.setattr("portwatch_backend.collector.service.fetch_host_ports", _raise)

    snapshot = collector.collect_once()

    assert snapshot.host_ports_enabled is False
    assert len(snapshot.containers) == 1  # Docker data still collected
    assert any("netprobe" in w for w in snapshot.warnings)


def test_collect_once_raises_and_leaves_store_untouched_when_docker_unreachable() -> None:
    from docker.errors import DockerException

    def _factory() -> Any:
        raise DockerException("connection refused")

    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=_factory)

    with pytest.raises(DockerException):
        collector.collect_once()

    assert store.read().generation == 0  # untouched, not "0 containers"


def test_collect_once_raises_when_version_call_fails() -> None:
    from docker.errors import DockerException

    # DockerException specifically — that's what docker-py actually raises
    # for a network/API-level failure; a generic bug in our own code should
    # propagate with its own type instead of being mislabeled as "proxy
    # unreachable" (it's still caught one level up by the background loop).
    fake_client = _FakeDockerClient(version_error=DockerException("proxy hiccup"))
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    with pytest.raises(RuntimeError, match="docker-socket-proxy unreachable"):
        collector.collect_once()


# --- collect_once: client.close() failure isolation ---------------------------


def test_collect_once_succeeds_even_if_client_close_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_client = _FakeDockerClient(
        containers=[_FakeContainer(_container_attrs("fixture-web"))],
        close_error=RuntimeError("connection already closed"),
    )
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    with caplog.at_level(logging.WARNING):
        snapshot = collector.collect_once()

    assert snapshot.generation == 1
    assert store.read().generation == 1
    assert fake_client.closed is True
    assert any("failed to close Docker client" in message for message in caplog.messages)


def test_collect_once_propagates_the_original_error_even_if_close_also_fails() -> None:
    # Regression: client.close() raising inside the original bare
    # `finally: client.close()` replaced whatever exception
    # _collect_with_client raised (plain Python try/finally semantics) — the
    # real root cause (e.g. "proxy unreachable") got masked by a much less
    # useful cleanup error. Manually confirmed against the pre-fix code: this
    # test failed with "connection already closed" instead of matching
    # "docker-socket-proxy unreachable".
    from docker.errors import DockerException

    fake_client = _FakeDockerClient(
        version_error=DockerException("proxy hiccup"),
        close_error=RuntimeError("connection already closed"),
    )
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    with pytest.raises(RuntimeError, match="docker-socket-proxy unreachable"):
        collector.collect_once()


# --- background loop lifecycle ------------------------------------------------


def test_start_runs_the_loop_and_stop_joins_the_thread_cleanly() -> None:
    call_count = 0
    lock = threading.Lock()

    def _factory() -> _FakeDockerClient:
        nonlocal call_count
        with lock:
            call_count += 1
        return _FakeDockerClient()

    settings = Settings(netprobe_url=None, collector_poll_interval_seconds=0.05)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=_factory)

    collector.start()
    time.sleep(0.3)
    collector.stop(timeout=2)

    assert store.read().generation >= 2
    assert collector._thread is None


def test_start_is_idempotent() -> None:
    settings = Settings(netprobe_url=None, collector_poll_interval_seconds=10)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=_FakeDockerClient)

    collector.start()
    first_thread = collector._thread
    collector.start()  # must not spawn a second thread
    assert collector._thread is first_thread

    collector.stop()


def test_a_failing_cycle_does_not_kill_the_background_thread() -> None:
    attempts = 0

    def _factory() -> _FakeDockerClient:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("first cycle fails")
        return _FakeDockerClient()

    settings = Settings(netprobe_url=None, collector_poll_interval_seconds=0.05)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=_factory)

    collector.start()
    time.sleep(0.3)
    collector.stop(timeout=2)

    # First cycle failed (store still at generation 0), later cycles
    # succeeded — the thread must have survived the first failure.
    assert store.read().generation >= 1


# --- collection budget and resource caps (ADR-0007) ---------------------------


def test_require_budget_does_not_raise_before_the_deadline() -> None:
    from portwatch_backend.collector.service import _require_budget

    _require_budget(time.monotonic() + 10, stage="some stage")  # must not raise


def test_require_budget_raises_once_the_deadline_has_passed() -> None:
    from portwatch_backend.collector.service import _require_budget

    with pytest.raises(CollectionBudgetExceeded, match="some stage"):
        _require_budget(time.monotonic() - 1, stage="some stage")


def test_collect_once_raises_when_the_cycle_budget_is_already_exhausted() -> None:
    fake_client = _FakeDockerClient(
        containers=[_FakeContainer(_container_attrs("fixture-web"))],
    )
    settings = Settings(netprobe_url=None, collector_cycle_budget_seconds=1e-9)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    with pytest.raises(CollectionBudgetExceeded):
        collector.collect_once()

    assert store.read().generation == 0  # no truncated/partial snapshot published


def test_collect_once_raises_when_container_count_exceeds_the_configured_max() -> None:
    containers = [_FakeContainer(_container_attrs(f"c{i}")) for i in range(3)]
    fake_client = _FakeDockerClient(containers=containers)
    settings = Settings(netprobe_url=None, collector_max_containers=2)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    with pytest.raises(CollectionBudgetExceeded, match="COLLECTOR_MAX_CONTAINERS"):
        collector.collect_once()

    assert store.read().generation == 0


def test_collect_once_raises_when_network_count_exceeds_the_configured_max() -> None:
    networks = [_FakeNetwork(_network_attrs(f"n{i}")) for i in range(3)]
    fake_client = _FakeDockerClient(networks=networks)
    settings = Settings(netprobe_url=None, collector_max_networks=2)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    with pytest.raises(CollectionBudgetExceeded, match="COLLECTOR_MAX_NETWORKS"):
        collector.collect_once()

    assert store.read().generation == 0


def test_collect_once_succeeds_when_resource_counts_exactly_equal_the_configured_max() -> None:
    # The check is "> max", so a count exactly at the max must still succeed
    # — the limit is inclusive.
    containers = [_FakeContainer(_container_attrs(f"c{i}")) for i in range(2)]
    fake_client = _FakeDockerClient(containers=containers)
    settings = Settings(netprobe_url=None, collector_max_containers=2)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)

    snapshot = collector.collect_once()

    assert len(snapshot.containers) == 2


def test_budget_exceeded_during_container_inspection_is_not_downgraded_to_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: CollectionBudgetExceeded is itself an Exception, so the
    # per-container `except Exception` (which isolates one bad container
    # without failing the whole cycle) would silently swallow it — turning a
    # real budget-exceeded abort into "cycle still succeeded, 0 containers"
    # — unless service.py re-raises it before that broad except runs.
    fake_client = _FakeDockerClient(containers=[_FakeContainer(_container_attrs("fixture-web"))])
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)
    warnings: list[str] = []
    deadline = 100.0

    # Calls in order for one container: the pre-listing check, the
    # pre-reload per-item check (both still "before the deadline"), then the
    # post-reload check inside the try block — trip the budget there.
    monkeypatch.setattr(
        "portwatch_backend.collector.service.time.monotonic",
        Mock(side_effect=[50.0, 60.0, 150.0]),
    )

    with pytest.raises(CollectionBudgetExceeded):
        collector._collect_containers(fake_client, warnings, deadline=deadline)

    assert warnings == []


def test_budget_exceeded_during_network_inspection_is_not_downgraded_to_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeDockerClient(networks=[_FakeNetwork(_network_attrs("portwatch-dev-net"))])
    settings = Settings(netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store, client_factory=lambda: fake_client)
    warnings: list[str] = []
    deadline = 100.0

    monkeypatch.setattr(
        "portwatch_backend.collector.service.time.monotonic",
        Mock(side_effect=[50.0, 60.0, 150.0]),
    )

    with pytest.raises(CollectionBudgetExceeded):
        collector._collect_networks(fake_client, warnings, deadline=deadline)

    assert warnings == []

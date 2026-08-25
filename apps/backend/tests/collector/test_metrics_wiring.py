"""Collector -> PortWatchMetrics wiring (service.py's `_run` loop). Unit
tests for PortWatchMetrics.observe_cycle_* live here too — they're small
enough not to need their own file, and this is where they're exercised.
"""

import time
from datetime import UTC, datetime

from portwatch_backend.collector.service import Collector
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.config import Settings
from portwatch_backend.core.metrics import PortWatchMetrics


class _FakeDockerClient:
    def __init__(self, *, version_error: Exception | None = None) -> None:
        self._version_error = version_error

        class _Empty:
            def list(self, all: bool = False) -> list:  # noqa: A002
                return []

        self.containers = _Empty()
        self.networks = _Empty()

    def version(self) -> dict:
        if self._version_error is not None:
            raise self._version_error
        return {"Version": "29.6.2", "ApiVersion": "1.55"}

    def close(self) -> None:
        pass


def _sample_value(
    metrics: PortWatchMetrics, name: str, labels: dict[str, str] | None = None
) -> float | None:
    for family in metrics.registry.collect():
        for sample in family.samples:
            if sample.name == name and (labels is None or sample.labels == labels):
                return sample.value
    return None


def test_observe_cycle_success_updates_the_expected_series() -> None:
    metrics = PortWatchMetrics()

    metrics.observe_cycle_success(
        duration_seconds=0.05,
        generation=3,
        containers=2,
        ports=5,
        collected_at=datetime(2026, 8, 25, tzinfo=UTC),
    )

    assert _sample_value(metrics, "portwatch_collector_cycles_total", {"outcome": "success"}) == 1.0
    assert _sample_value(metrics, "portwatch_snapshot_generation") == 3.0
    assert _sample_value(metrics, "portwatch_containers_total") == 2.0
    assert _sample_value(metrics, "portwatch_ports_total") == 5.0


def test_observe_cycle_failure_increments_the_failure_outcome_only() -> None:
    metrics = PortWatchMetrics()

    metrics.observe_cycle_failure(duration_seconds=0.01)

    failures = _sample_value(metrics, "portwatch_collector_cycles_total", {"outcome": "failure"})
    successes = _sample_value(metrics, "portwatch_collector_cycles_total", {"outcome": "success"})
    assert failures == 1.0
    assert successes is None


def test_background_loop_reports_both_outcomes_to_metrics() -> None:
    attempts = 0

    def _factory() -> _FakeDockerClient:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return _FakeDockerClient(version_error=RuntimeError("first cycle fails"))
        return _FakeDockerClient()

    settings = Settings(netprobe_url=None, collector_poll_interval_seconds=0.05)
    store = SnapshotStore()
    metrics = PortWatchMetrics()
    collector = Collector(settings, store, client_factory=_factory, metrics=metrics)

    collector.start()
    time.sleep(0.3)
    collector.stop(timeout=2)

    failures = _sample_value(metrics, "portwatch_collector_cycles_total", {"outcome": "failure"})
    successes = _sample_value(metrics, "portwatch_collector_cycles_total", {"outcome": "success"})
    assert failures is not None and failures >= 1.0
    assert successes is not None and successes >= 1.0

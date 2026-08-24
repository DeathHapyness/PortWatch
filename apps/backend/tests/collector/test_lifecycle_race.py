"""Regression tests for Collector start/stop lifecycle races."""

import threading

import pytest

from portwatch_backend.collector.service import Collector
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.config import Settings


def test_stop_timeout_does_not_allow_a_second_collector_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered_cycle = threading.Event()
    release_cycle = threading.Event()
    collector = Collector(Settings(netprobe_url=None), SnapshotStore())

    def blocking_cycle() -> None:
        entered_cycle.set()
        assert release_cycle.wait(timeout=2)

    monkeypatch.setattr(collector, "collect_once", blocking_cycle)

    collector.start()
    assert entered_cycle.wait(timeout=1)
    original_thread = collector._thread
    assert original_thread is not None

    collector.stop(timeout=0.01)

    assert original_thread.is_alive()
    assert collector._thread is original_thread

    # The timed-out stop must not make start() believe no worker exists.
    collector.start()
    assert collector._thread is original_thread

    release_cycle.set()
    collector.stop(timeout=1)
    assert collector._thread is None

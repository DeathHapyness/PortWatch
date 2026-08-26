"""Consistent in-memory snapshots shared by the Collector and API.

The Collector builds a complete snapshot away from the request path and then
publishes it in one operation. Readers therefore see either the previous or the
next generation, never a partially updated mix of containers, networks and
ports.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from portwatch_backend.core.schemas import (
    ContainerDetail,
    ContainerStatus,
    NetworkSummary,
    PortEntry,
)

Clock = Callable[[], datetime]
SnapshotPublishedCallback = Callable[[int, datetime], None]

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _is_stale(*, collected_at: datetime, now: datetime, max_age: timedelta) -> bool:
    _require_aware(now, field_name="now")
    if max_age < timedelta(0):
        raise ValueError("max_age must be non-negative")
    return now - collected_at > max_age


@dataclass(frozen=True, slots=True)
class CollectorSnapshot:
    """One coherent Collector generation.

    The dataclass and its collections are structurally immutable. Pydantic
    entities are deep-copied at the store boundary so producer or consumer
    mutation cannot corrupt the snapshot retained by the store.
    """

    generation: int
    collected_at: datetime
    docker_version: str | None = None
    docker_api_version: str | None = None
    containers: tuple[ContainerDetail, ...] = ()
    networks: tuple[NetworkSummary, ...] = ()
    ports: tuple[PortEntry, ...] = ()
    host_ports_enabled: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        _require_aware(self.collected_at, field_name="collected_at")

    def is_stale(self, *, now: datetime, max_age: timedelta) -> bool:
        """Return whether this generation is older than the accepted age."""

        return _is_stale(collected_at=self.collected_at, now=now, max_age=max_age)


@dataclass(frozen=True, slots=True)
class SnapshotOverview:
    """Immutable scalar view for frequently polled status endpoints."""

    generation: int
    collected_at: datetime
    docker_version: str | None
    docker_api_version: str | None
    containers_running: int
    containers_total: int
    networks_total: int
    ports_used_total: int
    host_ports_enabled: bool

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ValueError("generation must be non-negative")
        _require_aware(self.collected_at, field_name="collected_at")
        if not 0 <= self.containers_running <= self.containers_total:
            raise ValueError("containers_running must be between zero and containers_total")
        if self.networks_total < 0 or self.ports_used_total < 0:
            raise ValueError("resource totals must be non-negative")

    def is_stale(self, *, now: datetime, max_age: timedelta) -> bool:
        return _is_stale(collected_at=self.collected_at, now=now, max_age=max_age)


def _clone_snapshot(snapshot: CollectorSnapshot) -> CollectorSnapshot:
    """Detach mutable Pydantic values from callers at the store boundary."""

    return CollectorSnapshot(
        generation=snapshot.generation,
        collected_at=snapshot.collected_at,
        docker_version=snapshot.docker_version,
        docker_api_version=snapshot.docker_api_version,
        containers=tuple(item.model_copy(deep=True) for item in snapshot.containers),
        networks=tuple(item.model_copy(deep=True) for item in snapshot.networks),
        ports=tuple(item.model_copy(deep=True) for item in snapshot.ports),
        host_ports_enabled=snapshot.host_ports_enabled,
        warnings=snapshot.warnings,
    )


class SnapshotStore:
    """Thread-safe owner of the latest complete Collector snapshot."""

    def __init__(
        self,
        *,
        clock: Clock = _utc_now,
        on_publish: SnapshotPublishedCallback | None = None,
    ) -> None:
        self._clock = clock
        self._on_publish = on_publish
        self._lock = Lock()
        initial_time = clock()
        _require_aware(initial_time, field_name="clock result")
        self._snapshot = CollectorSnapshot(generation=0, collected_at=initial_time)
        self._overview = SnapshotOverview(
            generation=0,
            collected_at=initial_time,
            docker_version=None,
            docker_api_version=None,
            containers_running=0,
            containers_total=0,
            networks_total=0,
            ports_used_total=0,
            host_ports_enabled=False,
        )

    def read(self) -> CollectorSnapshot:
        """Return an isolated copy of one complete generation."""

        with self._lock:
            current = self._snapshot
        return _clone_snapshot(current)

    def read_overview(self) -> SnapshotOverview:
        """Return an O(1) coherent view without cloning resource models."""

        with self._lock:
            return self._overview

    def publish(
        self,
        *,
        containers: Sequence[ContainerDetail] = (),
        networks: Sequence[NetworkSummary] = (),
        ports: Sequence[PortEntry] = (),
        docker_version: str | None = None,
        docker_api_version: str | None = None,
        host_ports_enabled: bool = False,
        warnings: Sequence[str] = (),
        collected_at: datetime | None = None,
    ) -> CollectorSnapshot:
        """Atomically replace all collected state and return the new generation."""

        timestamp = collected_at if collected_at is not None else self._clock()
        _require_aware(timestamp, field_name="collected_at")

        # Clone before taking the lock so potentially large collections do not
        # block readers. The only serialized work is generation allocation and
        # the atomic reference replacement.
        detached_containers = tuple(item.model_copy(deep=True) for item in containers)
        detached_networks = tuple(item.model_copy(deep=True) for item in networks)
        detached_ports = tuple(item.model_copy(deep=True) for item in ports)
        detached_warnings = tuple(warnings)
        containers_running = sum(
            1 for container in detached_containers if container.status == ContainerStatus.running
        )

        with self._lock:
            snapshot = CollectorSnapshot(
                generation=self._snapshot.generation + 1,
                collected_at=timestamp,
                docker_version=docker_version,
                docker_api_version=docker_api_version,
                containers=detached_containers,
                networks=detached_networks,
                ports=detached_ports,
                host_ports_enabled=host_ports_enabled,
                warnings=detached_warnings,
            )
            self._snapshot = snapshot
            self._overview = SnapshotOverview(
                generation=snapshot.generation,
                collected_at=timestamp,
                docker_version=docker_version,
                docker_api_version=docker_api_version,
                containers_running=containers_running,
                containers_total=len(detached_containers),
                networks_total=len(detached_networks),
                ports_used_total=len(detached_ports),
                host_ports_enabled=host_ports_enabled,
            )

        if self._on_publish is not None:
            try:
                self._on_publish(snapshot.generation, snapshot.collected_at)
            except Exception:  # noqa: BLE001 - event delivery must not break collection
                logger.exception("snapshot publish listener failed")

        return _clone_snapshot(snapshot)

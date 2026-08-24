"""Consistent in-memory snapshots shared by the Collector and API.

The Collector builds a complete snapshot away from the request path and then
publishes it in one operation. Readers therefore see either the previous or the
next generation, never a partially updated mix of containers, networks and
ports.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from portwatch_backend.core.schemas import ContainerDetail, NetworkSummary, PortEntry

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


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

        _require_aware(now, field_name="now")
        if max_age < timedelta(0):
            raise ValueError("max_age must be non-negative")
        return now - self.collected_at > max_age


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

    def __init__(self, *, clock: Clock = _utc_now) -> None:
        self._clock = clock
        self._lock = Lock()
        initial_time = clock()
        _require_aware(initial_time, field_name="clock result")
        self._snapshot = CollectorSnapshot(generation=0, collected_at=initial_time)

    def read(self) -> CollectorSnapshot:
        """Return an isolated copy of one complete generation."""

        with self._lock:
            current = self._snapshot
        return _clone_snapshot(current)

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

        return _clone_snapshot(snapshot)

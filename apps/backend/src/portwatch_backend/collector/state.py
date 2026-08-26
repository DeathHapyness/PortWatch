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

from portwatch_backend.core.schemas import ContainerDetail, NetworkSummary, PortEntry

Clock = Callable[[], datetime]
SnapshotPublishedCallback = Callable[[int, datetime], None]

logger = logging.getLogger(__name__)


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
        self._containers_by_identifier: dict[str, ContainerDetail] = {}
        self._networks_by_identifier: dict[str, NetworkSummary] = {}

    def read(self) -> CollectorSnapshot:
        """Return an isolated copy of one complete generation."""

        with self._lock:
            current = self._snapshot
        return _clone_snapshot(current)

    def find_container(self, identifier: str) -> ContainerDetail | None:
        """Return one isolated container without cloning the full snapshot."""

        with self._lock:
            container = self._containers_by_identifier.get(identifier)
        return container.model_copy(deep=True) if container is not None else None

    def find_network(self, identifier: str) -> NetworkSummary | None:
        """Return one isolated network without cloning the full snapshot."""

        with self._lock:
            network = self._networks_by_identifier.get(identifier)
        return network.model_copy(deep=True) if network is not None else None

    def read_containers(self) -> tuple[ContainerDetail, ...]:
        """Return only containers, without cloning unrelated collections."""

        with self._lock:
            containers = self._snapshot.containers
        return tuple(item.model_copy(deep=True) for item in containers)

    def read_networks(self) -> tuple[NetworkSummary, ...]:
        """Return only networks, without cloning unrelated collections."""

        with self._lock:
            networks = self._snapshot.networks
        return tuple(item.model_copy(deep=True) for item in networks)

    def read_ports(self) -> tuple[PortEntry, ...]:
        """Return only ports, without cloning unrelated collections."""

        with self._lock:
            ports = self._snapshot.ports
        return tuple(item.model_copy(deep=True) for item in ports)

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
        containers_by_identifier: dict[str, ContainerDetail] = {}
        for container in detached_containers:
            # Preserve the list endpoint's existing first-match behavior if a
            # name happens to collide with another container's ID.
            containers_by_identifier.setdefault(container.id, container)
            containers_by_identifier.setdefault(container.name, container)
        networks_by_identifier: dict[str, NetworkSummary] = {}
        for network in detached_networks:
            networks_by_identifier.setdefault(network.id, network)
            networks_by_identifier.setdefault(network.name, network)

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
            self._containers_by_identifier = containers_by_identifier
            self._networks_by_identifier = networks_by_identifier

        if self._on_publish is not None:
            try:
                self._on_publish(snapshot.generation, snapshot.collected_at)
            except Exception:  # noqa: BLE001 - event delivery must not break collection
                logger.exception("snapshot publish listener failed")

        return _clone_snapshot(snapshot)

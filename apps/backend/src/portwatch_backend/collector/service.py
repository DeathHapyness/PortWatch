"""Collector — background worker that polls Docker (via docker-socket-proxy)
and, optionally, netprobe, then publishes one coherent snapshot per cycle to
a SnapshotStore.

docker-py is synchronous (see architecture blueprint, section 04 — the
official SDK was chosen over async alternatives precisely because the
Collector is a background service, not on the request path), so it runs in
one dedicated daemon thread. The FastAPI app stays fully async and only ever
reads SnapshotStore.read() — it never blocks on Docker or netprobe I/O.

A failed poll cycle is logged and *keeps the previous snapshot* rather than
publishing empty/partial data — callers can tell a snapshot is stale via
CollectorSnapshot.is_stale(). A single malformed container (unexpected
Status value, missing field, ...) is likewise skipped with a warning rather
than failing the whole cycle.
"""

import logging
import threading
import time
from collections.abc import Callable

import docker
from docker.errors import DockerException

from portwatch_backend.collector.docker_client import make_docker_client
from portwatch_backend.collector.netprobe_client import (
    HostPortEntry,
    NetprobeError,
    fetch_host_ports,
)
from portwatch_backend.collector.parsing import (
    build_port_entries,
    parse_container_detail,
    parse_network_summary,
)
from portwatch_backend.collector.state import CollectorSnapshot, SnapshotStore
from portwatch_backend.core.config import Settings
from portwatch_backend.core.metrics import PortWatchMetrics
from portwatch_backend.core.schemas import ContainerDetail, NetworkSummary

logger = logging.getLogger(__name__)

ClientFactory = Callable[[], docker.DockerClient]


class Collector:
    """Owns the poll loop and the one SnapshotStore it publishes into."""

    def __init__(
        self,
        settings: Settings,
        store: SnapshotStore,
        *,
        client_factory: ClientFactory | None = None,
        metrics: PortWatchMetrics | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client_factory = client_factory or (lambda: make_docker_client(settings))
        self._metrics = metrics
        self._stop_event = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def store(self) -> SnapshotStore:
        return self._store

    def start(self) -> None:
        """Start the background poll loop. Idempotent."""

        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name="portwatch-collector", daemon=True
            )
            self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        """Signal the loop to stop and wait for the current cycle to finish."""

        with self._lifecycle_lock:
            thread = self._thread
            if thread is None:
                return

            self._stop_event.set()
            thread.join(timeout=timeout)
            if thread.is_alive():
                # Keep the live thread reference. A subsequent start() must
                # not create a second Collector while this cycle is still
                # blocked in Docker/netprobe I/O.
                logger.warning(
                    "collector: background thread did not stop within %.1fs",
                    timeout,
                )
                return
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            start = time.monotonic()
            try:
                snapshot = self.collect_once()
            except Exception:  # noqa: BLE001 - a bad cycle must never kill the thread
                logger.warning("collector: poll cycle failed, keeping last snapshot", exc_info=True)
                if self._metrics is not None:
                    self._metrics.observe_cycle_failure(duration_seconds=time.monotonic() - start)
            else:
                if self._metrics is not None:
                    self._metrics.observe_cycle_success(
                        duration_seconds=time.monotonic() - start,
                        generation=snapshot.generation,
                        containers=len(snapshot.containers),
                        ports=len(snapshot.ports),
                        collected_at=snapshot.collected_at,
                    )
            self._stop_event.wait(self._settings.collector_poll_interval_seconds)

    def collect_once(self) -> CollectorSnapshot:
        """Run exactly one collection cycle and publish it. Raises on total
        failure (e.g. socket-proxy unreachable) so callers/tests can observe
        it directly; the background loop (_run) is what swallows and logs."""

        client = self._client_factory()
        try:
            return self._collect_with_client(client)
        finally:
            client.close()

    def _collect_with_client(self, client: docker.DockerClient) -> CollectorSnapshot:
        warnings: list[str] = []

        try:
            version_info = client.version()
        except DockerException as exc:
            raise RuntimeError(f"docker-socket-proxy unreachable: {exc}") from exc

        containers = self._collect_containers(client, warnings)
        networks = self._collect_networks(client, warnings)
        host_ports_enabled, host_ports = self._collect_host_ports(warnings)

        ports = build_port_entries(containers, host_ports)

        return self._store.publish(
            containers=containers,
            networks=networks,
            ports=ports,
            docker_version=version_info.get("Version"),
            docker_api_version=version_info.get("ApiVersion"),
            host_ports_enabled=host_ports_enabled,
            warnings=warnings,
        )

    def _collect_containers(
        self, client: docker.DockerClient, warnings: list[str]
    ) -> list[ContainerDetail]:
        summaries: list[ContainerDetail] = []
        for container in client.containers.list(all=True):
            try:
                # list() returns the leaner list-endpoint shape; reload()
                # re-fetches full GET /containers/{id}/json inspect data
                # (Config.Labels, State.Health, NetworkSettings.Ports map)
                # that the parser needs — see parsing.parse_container_detail.
                container.reload()
                summaries.append(parse_container_detail(container.attrs))
            except Exception as exc:  # noqa: BLE001 - isolate one bad container
                warnings.append(f"skipped container {(container.id or '?')[:12]}: {exc}")
        return summaries

    def _collect_networks(
        self, client: docker.DockerClient, warnings: list[str]
    ) -> list[NetworkSummary]:
        summaries: list[NetworkSummary] = []
        for network in client.networks.list():
            try:
                # list() leaves Containers as null (confirmed against a real
                # daemon, not just docs) — reload() re-fetches full
                # GET /networks/{id}/json inspect data, same reasoning as
                # container.reload() above.
                network.reload()
                summaries.append(parse_network_summary(network.attrs))
            except Exception as exc:  # noqa: BLE001 - isolate one bad network
                warnings.append(f"skipped network {(network.id or '?')[:12]}: {exc}")
        return summaries

    def _collect_host_ports(self, warnings: list[str]) -> tuple[bool, list[HostPortEntry]]:
        netprobe_url = self._settings.netprobe_url
        if not netprobe_url:
            return False, []
        try:
            return True, fetch_host_ports(netprobe_url)
        except NetprobeError as exc:
            warnings.append(f"netprobe unavailable, host ports disabled this cycle: {exc}")
            return False, []

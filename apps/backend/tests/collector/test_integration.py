"""Integration test: the real Collector (real docker-py client) against the
actual dev sandbox (infra/dev/docker-compose.dev.yml) via the real
docker-socket-proxy — per the roadmap's Phase 3 criterion ("Collector lista
containers/redes/portas reais do sandbox").

This never touches a Docker socket directly, and never any Docker other than
this machine's local sandbox (see CLAUDE.md) — it only ever talks to
docker-socket-proxy over HTTP, exactly like the real Collector does.

Skipped automatically (not failed) when the sandbox isn't up, so the rest of
the suite stays green without requiring `make dev-up` first. Run manually
with the sandbox up:

    make dev-up
    uv run pytest tests/collector/test_integration.py -v
    make dev-down
"""

import os

import httpx
import pytest

from portwatch_backend.collector.service import Collector
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.config import Settings

DOCKER_PROXY_URL = os.environ.get("PORTWATCH_TEST_DOCKER_PROXY_URL", "http://127.0.0.1:2375")
NETPROBE_URL = os.environ.get("PORTWATCH_TEST_NETPROBE_URL", "http://127.0.0.1:8088")


def _sandbox_reachable(url: str) -> bool:
    try:
        response = httpx.get(f"{url}/version", timeout=1.0)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


requires_sandbox = pytest.mark.skipif(
    not _sandbox_reachable(DOCKER_PROXY_URL),
    reason=(
        f"dev sandbox not reachable at {DOCKER_PROXY_URL} — run `make dev-up` first "
        "to exercise this integration test"
    ),
)


@requires_sandbox
def test_collector_lists_real_sandbox_containers_and_networks() -> None:
    settings = Settings(docker_proxy_url=DOCKER_PROXY_URL, netprobe_url=None)
    store = SnapshotStore()
    collector = Collector(settings, store)

    snapshot = collector.collect_once()

    assert snapshot.warnings == ()
    assert snapshot.docker_version is not None

    # fixture-web is always part of the sandbox (infra/dev/docker-compose.dev.yml)
    # and every container in it must carry the dev-sandbox label (guard.sh
    # enforces this for anything actually running against this daemon).
    names = [c.name for c in snapshot.containers]
    assert "portwatch-dev-fixture-web" in names
    for container in snapshot.containers:
        assert container.labels.get("portwatch.env") == "dev-sandbox"

    network_names = [n.name for n in snapshot.networks]
    assert "portwatch-dev-net" in network_names
    sandbox_net = next(n for n in snapshot.networks if n.name == "portwatch-dev-net")
    assert "portwatch-dev-fixture-web" in sandbox_net.containers

    published = {(p.port, p.protocol.value): p for p in snapshot.ports if p.state == "published"}
    assert (8081, "tcp") in published
    assert published[(8081, "tcp")].owner == "portwatch-dev-fixture-web"


@requires_sandbox
def test_collector_reports_host_ports_when_netprobe_is_up() -> None:
    try:
        httpx.get(f"{NETPROBE_URL}/health", timeout=1.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"netprobe not reachable at {NETPROBE_URL} — run `make dev-up` first")

    settings = Settings(docker_proxy_url=DOCKER_PROXY_URL, netprobe_url=NETPROBE_URL)
    store = SnapshotStore()
    collector = Collector(settings, store)

    snapshot = collector.collect_once()

    assert snapshot.host_ports_enabled is True
    # docker-socket-proxy itself is bound on the host at 127.0.0.1:2375 —
    # it must show up as "host" or "published" port state either way.
    proxy_port = int(DOCKER_PROXY_URL.rsplit(":", 1)[1])
    assert any(p.port == proxy_port for p in snapshot.ports)

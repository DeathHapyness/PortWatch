"""End-to-end coverage against the *real* infra/dev/docker-compose.dev.yml
stack: real docker-socket-proxy, real netprobe, a real backend Collector
cycle — everywhere else in this test suite mocks or fakes those. This is
the gap README.md used to list as "falta: testes E2E contra o sandbox
real".

Requires the `e2e` marker (excluded from the default `uv run pytest` run —
see pyproject.toml). Run with `make test-e2e` or `uv run pytest -m e2e`.
See conftest.py for how the sandbox and the app are brought up/down.
"""

from __future__ import annotations

import httpx
import pytest

# Kept as plain module-level constants (not imported from conftest.py) —
# pytest collects this test tree without package __init__.py files, so
# there's no reliable `tests.e2e.conftest` import path; fixtures are shared
# via conftest.py's normal auto-discovery instead.
DEV_SANDBOX_NETWORK = "portwatch-dev-net"
FIXTURE_CONTAINER_NAME = "portwatch-dev-fixture-web"
FIXTURE_HOST_PORT = 8081
NETPROBE_HOST_PORT = 8088

pytestmark = pytest.mark.e2e


async def test_health_is_always_up_regardless_of_auth_or_docker(
    sandbox_client: httpx.AsyncClient,
) -> None:
    response = await sandbox_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reflects_a_real_completed_collector_cycle(
    sandbox_client: httpx.AsyncClient,
) -> None:
    # sandbox_client's fixture already blocked on /health/ready == 200
    # before yielding — re-fetching just asserts the real body shape.
    response = await sandbox_client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["generation"] >= 1
    assert body["host_ports_enabled"] is True  # netprobe is wired up


async def test_protected_routes_require_the_real_bearer_token(
    sandbox_client: httpx.AsyncClient,
) -> None:
    no_auth = await sandbox_client.get("/api/v1/containers")
    assert no_auth.status_code == 401
    problem = no_auth.json()
    assert problem["status"] == 401
    assert problem["title"]

    wrong_token = await sandbox_client.get(
        "/api/v1/containers", headers={"Authorization": "Bearer not-the-token"}
    )
    assert wrong_token.status_code == 401


async def test_containers_endpoint_lists_the_real_fixture_container(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await sandbox_client.get("/api/v1/containers", headers=auth_headers)

    assert response.status_code == 200
    containers = response.json()
    fixture = next((c for c in containers if c["name"] == FIXTURE_CONTAINER_NAME), None)
    assert fixture is not None, f"{FIXTURE_CONTAINER_NAME} not seen through docker-socket-proxy"
    assert fixture["status"] == "running"
    assert fixture["image"].startswith("nginx")
    assert DEV_SANDBOX_NETWORK in fixture["networks"]
    assert any(p["host_port"] == FIXTURE_HOST_PORT for p in fixture["ports"])
    # PW-03: labels are redacted by key, but the sandbox's own marker label
    # is not secret-shaped and is the guard's own signal — it must survive.
    assert fixture["labels"].get("portwatch.env") == "dev-sandbox"


async def test_container_detail_lookup_by_name_matches_list_view(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await sandbox_client.get(
        f"/api/v1/containers/{FIXTURE_CONTAINER_NAME}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == FIXTURE_CONTAINER_NAME


async def test_networks_endpoint_lists_the_real_dev_sandbox_network(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await sandbox_client.get("/api/v1/networks", headers=auth_headers)

    assert response.status_code == 200
    names = [n["name"] for n in response.json()]
    assert DEV_SANDBOX_NETWORK in names


async def test_ports_endpoint_reflects_the_real_published_fixture_port(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await sandbox_client.get(
        "/api/v1/ports",
        params={"range_start": FIXTURE_HOST_PORT, "range_end": FIXTURE_HOST_PORT},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == [
        {
            "port": FIXTURE_HOST_PORT,
            "protocol": "tcp",
            "state": "published",
            "owner": FIXTURE_CONTAINER_NAME,
        }
    ]


async def test_ports_endpoint_sees_a_real_host_listener_via_netprobe(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # netprobe itself (network_mode: host, port 8088, no `ports:` mapping —
    # network_mode: host bypasses Docker's own port-publishing entirely) is
    # the one port in this sandbox the Collector can *only* know about
    # through netprobe's host-namespace view, never through the Docker API.
    # (docker-socket-proxy's 2375 doesn't work for this: it's a normal
    # Docker-published port too, so the Collector already knows it as
    # state=published from the container inspect alone — confirmed by hand
    # against a real cycle before picking 8088 instead.)
    response = await sandbox_client.get(
        "/api/v1/ports",
        params={
            "range_start": NETPROBE_HOST_PORT,
            "range_end": NETPROBE_HOST_PORT,
            "state": "host",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert [e["port"] for e in response.json()["entries"]] == [NETPROBE_HOST_PORT]


async def test_available_ports_excludes_the_real_occupied_fixture_port(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await sandbox_client.get(
        "/api/v1/ports/available",
        params={"range_start": FIXTURE_HOST_PORT - 1, "range_end": FIXTURE_HOST_PORT + 1},
        headers=auth_headers,
    )

    assert response.status_code == 200
    free_ports = [e["port"] for e in response.json()["entries"]]
    assert FIXTURE_HOST_PORT not in free_ports
    assert FIXTURE_HOST_PORT - 1 in free_ports
    assert FIXTURE_HOST_PORT + 1 in free_ports


async def test_system_summary_reports_the_real_docker_version(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await sandbox_client.get("/api/v1/system/summary", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["docker_version"]  # non-empty: came from the real daemon
    assert body["host_ports_enabled"] is True
    assert body["containers_running"] >= 1


def _metric_value(body: str, prefix: str) -> float:
    # Minimal Prometheus text-format line lookup: find the one line starting
    # with `prefix` (name, optionally with a `{...}` label set) and parse
    # the trailing value. Not a general parser — good enough for one known
    # series in output we control.
    for line in body.splitlines():
        if line.startswith(prefix):
            return float(line.rsplit(" ", 1)[-1])
    raise AssertionError(f"no metric line starting with {prefix!r} in:\n{body}")


async def test_metrics_reports_a_real_completed_collector_cycle(
    sandbox_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # sandbox_client's fixture blocks on /health/ready == 200 before
    # yielding, so at least one real cycle against the real sandbox has
    # already run and been observed by the background loop's metrics hook
    # (core/metrics.py's Collector wiring — see collector/service.py:_run).
    response = await sandbox_client.get("/metrics", headers=auth_headers)

    assert response.status_code == 200
    body = response.text
    assert _metric_value(body, 'portwatch_collector_cycles_total{outcome="success"}') >= 1.0
    assert _metric_value(body, "portwatch_snapshot_generation") >= 1.0

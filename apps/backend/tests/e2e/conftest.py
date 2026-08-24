"""Fixtures that bring up the *real* dev sandbox (docker-socket-proxy +
netprobe + the inert fixture container) and a real backend app wired to it —
as opposed to every other test in this suite, which never touches Docker.

Safety: this reuses infra/dev/guard.sh — the exact same check
`make dev-up` runs — before touching Docker at all, and refuses (skips) if
it fails or if the CLI isn't even installed. It never invents its own,
looser check. See CLAUDE.md's permanent scope rules.

Everything here is opt-in via the `e2e` marker (see pyproject.toml's
`addopts`, which excludes it by default) — a plain `uv run pytest` never
starts Docker containers. Run these explicitly with `make test-e2e` or
`uv run pytest -m e2e`.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest

from portwatch_backend.app import create_app

# apps/backend/tests/e2e/conftest.py -> repo root is four parents up.
REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "infra" / "dev" / "docker-compose.dev.yml"
GUARD_SCRIPT = REPO_ROOT / "infra" / "dev" / "guard.sh"

DOCKER_PROXY_URL = "http://127.0.0.1:2375"
NETPROBE_URL = "http://127.0.0.1:8088"
E2E_API_TOKEN = "e2e-sandbox-test-token"  # noqa: S105 - throwaway, sandbox-only

# The dev sandbox fixture container (infra/dev/docker-compose.dev.yml) —
# this suite asserts the Collector actually observes it through the real
# docker-socket-proxy, not a mock.
FIXTURE_CONTAINER_NAME = "portwatch-dev-fixture-web"
FIXTURE_HOST_PORT = 8081
DEV_SANDBOX_NETWORK = "portwatch-dev-net"

_READY_TIMEOUT_SECONDS = 30.0
_READY_POLL_INTERVAL_SECONDS = 0.5
_SERVICE_WAIT_TIMEOUT_SECONDS = 20.0
_SERVICE_WAIT_POLL_INTERVAL_SECONDS = 0.25


def _wait_for_http_ok(url: str) -> None:
    """Block (plain sync httpx — no event loop exists yet at this point in
    the sandbox fixture) until `url` answers with any HTTP response at all;
    a real reply, even a 4xx, proves the service is actually accepting
    connections, which is what the caller needs."""

    deadline = time.monotonic() + _SERVICE_WAIT_TIMEOUT_SECONDS
    last_error: Exception | None = None
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                client.get(url)
                return
            except httpx.HTTPError as exc:
                last_error = exc
                time.sleep(_SERVICE_WAIT_POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"{url} never answered within {_SERVICE_WAIT_TIMEOUT_SECONDS:.0f}s: {last_error}"
    )


def _resolve_guarded_docker_host() -> str:
    """Run the same guard.sh the Makefile uses and return its endpoint.

    Raises RuntimeError with guard.sh's own diagnostic on stderr if the
    active Docker doesn't look like this machine's local dev sandbox —
    callers must let that fail the session rather than falling back to any
    other endpoint.
    """

    result = subprocess.run(  # noqa: S603 - fixed args, no user input
        ["bash", str(GUARD_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "infra/dev/guard.sh refused to confirm a safe local dev Docker:\n"
            f"{result.stderr.strip()}"
        )
    endpoint = result.stdout.strip()
    if not endpoint:
        raise RuntimeError("infra/dev/guard.sh succeeded but printed no endpoint")
    return endpoint


@pytest.fixture(scope="session")
def dev_sandbox_docker_host() -> Iterator[str]:
    """Bring the real dev sandbox stack up for the whole e2e session, and
    tear it down afterwards — mirrors `make dev-up` / `make dev-down`
    exactly (same guard, same compose file), just from Python so a single
    `uv run pytest -m e2e` is enough without a separate shell step."""

    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available — skipping e2e sandbox tests")

    try:
        endpoint = _resolve_guarded_docker_host()
    except RuntimeError as exc:
        pytest.skip(f"dev sandbox guard did not pass: {exc}")

    env = {**os.environ, "DOCKER_HOST": endpoint}
    subprocess.run(  # noqa: S603
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--wait"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )
    try:
        # `--wait` above only waits for container state == running — neither
        # service has a compose healthcheck, so this doesn't mean either has
        # actually bound its port yet. The Collector's first cycle runs
        # immediately once the app starts (see collector/service.py's
        # Collector._run), so without this a real, observed flake happens:
        # netprobe (or docker-socket-proxy) not answering yet on that very
        # first cycle silently produces host_ports_enabled=False for the
        # snapshot every test in this module reads — /health/ready still
        # says "ready" (it only checks generation >= 1), so nothing here
        # would have failed loudly without this wait.
        _wait_for_http_ok(f"{DOCKER_PROXY_URL}/version")
        _wait_for_http_ok(f"{NETPROBE_URL}/health")
        yield endpoint
    finally:
        subprocess.run(  # noqa: S603
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
            cwd=REPO_ROOT,
            env=env,
            check=False,
        )


@pytest.fixture(scope="session")
def sandbox_env(dev_sandbox_docker_host: str) -> Iterator[None]:
    """Point the backend's Settings at the real sandbox services (same
    variables README.md tells a developer to export by hand) plus a token,
    so this suite also exercises ADR-0004 auth against real traffic instead
    of only the mocked unit tests in test_auth.py."""

    overrides = {
        "PORTWATCH_DOCKER_PROXY_URL": DOCKER_PROXY_URL,
        "PORTWATCH_NETPROBE_URL": NETPROBE_URL,
        "PORTWATCH_API_TOKEN": E2E_API_TOKEN,
        # collect_once() runs immediately on Collector.start() — the poll
        # interval only matters for the *second* cycle, which this suite
        # never waits for. Left at the Settings default deliberately, so
        # this exercises the real configured cadence, not a test-only one.
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="session")
async def sandbox_client(sandbox_env: None) -> AsyncIterator[httpx.AsyncClient]:
    """A real app instance, its real lifespan (Collector thread against the
    real sandbox), driven the same deadlock-safe way as test_lifespan.py:
    ASGITransport + explicit lifespan_context, never the synchronous
    TestClient portal."""

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://e2e-test") as client,
    ):
        await _wait_until_ready(client)
        yield client


async def _wait_until_ready(client: httpx.AsyncClient) -> None:
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    last_body: object = None
    while time.monotonic() < deadline:
        response = await client.get("/health/ready")
        last_body = response.json()
        if response.status_code == 200:
            return
        await asyncio.sleep(_READY_POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"backend never became ready within {_READY_TIMEOUT_SECONDS:.0f}s "
        f"against the real sandbox — last /health/ready body: {last_body!r}"
    )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {E2E_API_TOKEN}"}

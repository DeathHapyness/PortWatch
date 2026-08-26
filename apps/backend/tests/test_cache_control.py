"""sensitive_response_cache_control_middleware (core/cache_control.py) —
attaches Cache-Control: no-store to every /api/v1/* and /metrics response so
browsers/shared proxies never persist monitoring data (container names,
images, labels, port maps, ...). Health probes and public API docs are
intentionally left cacheable.
"""

import httpx
import pytest

from portwatch_backend.app import create_app
from portwatch_backend.core.cache_control import _contains_sensitive_monitoring_data
from portwatch_backend.core.config import Settings


@pytest.fixture
async def client():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_settings(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token=token),
    )


# --- _contains_sensitive_monitoring_data: unit tests ------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1",
        "/api/v1/",
        "/api/v1/containers",
        "/api/v1/containers/abc123",
        "/api/v1/system/summary",
        "/metrics",
    ],
)
def test_marks_protected_and_metrics_paths_as_sensitive(path: str) -> None:
    assert _contains_sensitive_monitoring_data(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/health",
        "/health/ready",
        "/docs",
        "/openapi.json",
        "/api/v10/evil",  # prefix confusion: must not match on "/api/v1" alone
        "/api/v1extra",  # same, without the separating slash
    ],
)
def test_does_not_mark_unrelated_paths_as_sensitive(path: str) -> None:
    assert _contains_sensitive_monitoring_data(path) is False


# --- middleware: client-level tests ------------------------------------------


async def test_protected_api_responses_are_not_cacheable(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="")

    resp = await client.get("/api/v1/system/summary")

    assert resp.headers["cache-control"] == "no-store"


async def test_metrics_responses_are_not_cacheable(client: httpx.AsyncClient) -> None:
    resp = await client.get("/metrics")

    assert resp.headers["cache-control"] == "no-store"


async def test_health_responses_stay_cacheable(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")

    assert "cache-control" not in resp.headers


async def test_an_auth_rejection_under_api_v1_still_gets_no_store(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The policy has to cover auth failures too, not just 200s — an
    # unauthorized response can still leak whether a resource exists.
    _patch_settings(monkeypatch, token="s3cr3t")

    resp = await client.get("/api/v1/system/summary")

    assert resp.status_code == 401
    assert resp.headers["cache-control"] == "no-store"


async def test_a_404_under_api_v1_still_gets_no_store(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="")

    resp = await client.get("/api/v1/containers/does-not-exist")

    assert resp.status_code == 404
    assert resp.headers["cache-control"] == "no-store"

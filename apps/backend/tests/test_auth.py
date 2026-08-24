"""require_api_token (core/auth.py) — unit tests call it directly; the
client-level tests monkeypatch core.auth.get_settings to control whether a
token is configured for one request, then let pytest's monkeypatch fixture
auto-revert it (no shared-state leakage risk, unlike app.state singletons).
"""

import httpx
import pytest
from fastapi import HTTPException

from portwatch_backend.app import app
from portwatch_backend.core.auth import require_api_token
from portwatch_backend.core.config import Settings


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_settings(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token=token),
    )


# --- unit tests: require_api_token in isolation -------------------------------


async def test_auth_is_a_noop_when_no_token_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, token="")
    await require_api_token(authorization=None)  # must not raise


async def test_missing_header_is_rejected_when_a_token_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")
    with pytest.raises(HTTPException) as exc_info:
        await require_api_token(authorization=None)
    assert exc_info.value.status_code == 401


async def test_non_bearer_header_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")
    with pytest.raises(HTTPException) as exc_info:
        await require_api_token(authorization="Basic s3cr3t")
    assert exc_info.value.status_code == 401


async def test_wrong_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")
    with pytest.raises(HTTPException) as exc_info:
        await require_api_token(authorization="Bearer wrong")
    assert exc_info.value.status_code == 401


async def test_correct_token_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")
    await require_api_token(authorization="Bearer s3cr3t")  # must not raise


# --- client-level tests: the dependency actually protects /api/v1/* ----------


async def test_protected_route_rejects_requests_without_a_token(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")

    resp = await client.get("/api/v1/system/summary")

    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_protected_route_accepts_the_correct_bearer_token(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")

    resp = await client.get("/api/v1/system/summary", headers={"Authorization": "Bearer s3cr3t"})

    assert resp.status_code == 200


async def test_health_stays_public_even_with_a_token_configured(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")

    resp = await client.get("/health")

    assert resp.status_code == 200


async def test_protected_routes_are_open_when_no_token_is_configured(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="")

    resp = await client.get("/api/v1/system/summary")

    assert resp.status_code == 200

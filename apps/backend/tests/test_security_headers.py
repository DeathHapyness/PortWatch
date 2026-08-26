"""security_headers_middleware (core/security_headers.py) — baseline
browser-facing headers applied to every HTTP response.
"""

import httpx
import pytest

from portwatch_backend.app import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_a_protected_api_response_gets_the_baseline_headers(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/api/v1/system/summary")

    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


async def test_health_responses_also_get_the_baseline_headers(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")

    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


async def test_a_404_response_still_gets_the_baseline_headers(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/containers/does-not-exist")

    assert resp.status_code == 404
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


async def test_openapi_docs_responses_get_the_baseline_headers(client: httpx.AsyncClient) -> None:
    resp = await client.get("/openapi.json")

    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"

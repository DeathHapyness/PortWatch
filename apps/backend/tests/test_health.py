import httpx
import pytest

from portwatch_backend.app import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_ready(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/ready")
    assert resp.status_code == 200


async def test_system_summary_matches_contract(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/system/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "docker_version" in body
    assert "ports_used_total" in body


async def test_container_not_found_is_problem_json(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/containers/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["status"] == 404

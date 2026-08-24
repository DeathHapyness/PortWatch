"""Additional problem-detail contract checks for port endpoints."""

from collections.abc import AsyncIterator

import httpx
import pytest

from portwatch_backend.app import app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


async def test_ports_rejects_non_integer_range_as_problem_detail(
    client: httpx.AsyncClient,
) -> None:
    request_id = "ports-invalid-range"

    response = await client.get(
        "/api/v1/ports",
        params={"range_start": "abc"},
        headers={"X-Request-Id": request_id},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-Id"] == request_id
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "Request validation error"
    assert body["status"] == 422
    assert body["detail"][0]["loc"] == ["query", "range_start"]


async def test_ports_rejects_unknown_state_as_problem_detail(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/ports", params={"state": "listening"})

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422
    assert body["detail"][0]["loc"] == ["query", "state"]


async def test_available_rejects_zero_limit_with_rfc7807_response(
    client: httpx.AsyncClient,
) -> None:
    request_id = "available-zero-limit"

    response = await client.get(
        "/api/v1/ports/available",
        params={"range_start": 1, "range_end": 2, "limit": 0},
        headers={"X-Request-Id": request_id},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-Id"] == request_id
    assert response.json()["detail"] == "limit must be between 1 and 1000"

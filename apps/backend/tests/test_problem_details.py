import httpx
import pytest

from portwatch_backend.app import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_validation_errors_use_problem_details_and_preserve_request_id(
    client: httpx.AsyncClient,
) -> None:
    request_id = "test-request-123"

    response = await client.get(
        "/api/v1/ports",
        params={"range_start": "not-an-int"},
        headers={"X-Request-Id": request_id},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-Id"] == request_id
    assert response.json() == {
        "type": "about:blank",
        "title": "Request validation error",
        "status": 422,
        "detail": [
            {
                "type": "int_parsing",
                "loc": ["query", "range_start"],
                "msg": "Input should be a valid integer, unable to parse string as an integer",
                "input": "not-an-int",
            }
        ],
        "request_id": request_id,
    }


async def test_request_id_is_generated_and_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    generated_request_id = response.headers["X-Request-Id"]
    assert generated_request_id
    assert response.json() == {"status": "ok"}

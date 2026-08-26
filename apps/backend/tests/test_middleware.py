"""request_id_middleware (core/middleware.py) — a client-supplied
X-Request-Id flows straight into structured logs (core/logging.py) and is
echoed back on every response (including error responses' RFC 7807
`request_id` field), so it has to be treated as attacker-controlled input,
not trusted metadata. _safe_request_id enforces that: a short ASCII
token-like value is kept, anything else silently falls back to a
server-generated UUID rather than rejecting the request.

Verified manually before writing these tests: reverting to the pre-fix
`request.headers.get("X-Request-Id", "").strip() or str(uuid4())` logic and
sending a 500-character X-Request-Id echoed it back verbatim, unbounded, in
the response header — exactly what MAX_REQUEST_ID_LENGTH now prevents.
"""

import httpx
import pytest

from portwatch_backend.app import app
from portwatch_backend.core.middleware import MAX_REQUEST_ID_LENGTH, _safe_request_id


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- _safe_request_id: unit tests -------------------------------------------


def test_none_generates_a_uuid() -> None:
    result = _safe_request_id(None)
    assert len(result) == 36  # uuid4 str() length; also implicitly not empty


def test_a_normal_token_like_value_is_preserved() -> None:
    assert _safe_request_id("abc-123.foo:bar") == "abc-123.foo:bar"


def test_a_single_character_is_preserved() -> None:
    assert _safe_request_id("a") == "a"


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "   ",
        "-starts-with-dash",
        ".starts-with-dot",
        "has space",
        "has\nnewline",
        "has\ttab",
        "has\x00null",
        "emoji-🔥",
        "a" * (MAX_REQUEST_ID_LENGTH + 1),
    ],
)
def test_invalid_values_fall_back_to_a_generated_uuid(candidate: str) -> None:
    result = _safe_request_id(candidate)
    assert result != candidate
    assert len(result) == 36


def test_exactly_the_max_length_is_still_preserved() -> None:
    candidate = "a" * MAX_REQUEST_ID_LENGTH
    assert _safe_request_id(candidate) == candidate


def test_one_over_the_max_length_falls_back() -> None:
    candidate = "a" * (MAX_REQUEST_ID_LENGTH + 1)
    result = _safe_request_id(candidate)
    assert result != candidate


# --- middleware: client-level tests -----------------------------------------


async def test_no_header_generates_and_echoes_a_uuid(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health")

    assert resp.status_code == 200
    assert len(resp.headers["x-request-id"]) == 36


async def test_a_valid_client_supplied_id_is_echoed_back(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-Id": "trace-abc-123"})

    assert resp.headers["x-request-id"] == "trace-abc-123"


async def test_an_oversized_client_supplied_id_is_replaced(client: httpx.AsyncClient) -> None:
    oversized = "a" * 500

    resp = await client.get("/health", headers={"X-Request-Id": oversized})

    echoed = resp.headers["x-request-id"]
    assert echoed != oversized
    assert len(echoed) == 36


async def test_a_malformed_client_supplied_id_is_replaced(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-Id": "has space"})

    echoed = resp.headers["x-request-id"]
    assert echoed != "has space"
    assert len(echoed) == 36

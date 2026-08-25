from __future__ import annotations

import json
import logging
from io import StringIO

import httpx
from fastapi import FastAPI, Request

from portwatch_backend.core.logging import JsonFormatter, configure_logging
from portwatch_backend.core.middleware import request_id_middleware


def _handler(output: StringIO) -> logging.Handler:
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonFormatter())
    return handler


def test_json_formatter_emits_stable_core_fields_and_exception() -> None:
    output = StringIO()
    logger = logging.getLogger("portwatch.test.formatter")
    logger.handlers = [_handler(output)]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    try:
        raise RuntimeError("collector failed")
    except RuntimeError:
        logger.exception("poll cycle failed")

    payload = json.loads(output.getvalue())
    assert payload["level"] == "ERROR"
    assert payload["logger"] == "portwatch.test.formatter"
    assert payload["message"] == "poll cycle failed"
    assert payload["timestamp"].endswith("+00:00")
    assert "RuntimeError: collector failed" in payload["exception"]
    assert "request_id" not in payload


def test_formatter_does_not_serialize_arbitrary_extra_fields() -> None:
    output = StringIO()
    logger = logging.getLogger("portwatch.test.secrets")
    logger.handlers = [_handler(output)]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info(
        "authentication attempted",
        extra={"authorization": "Bearer top-secret", "token": "top-secret"},
    )

    payload = json.loads(output.getvalue())
    assert payload["message"] == "authentication attempted"
    assert "authorization" not in payload
    assert "token" not in payload
    assert "top-secret" not in output.getvalue()


def test_formatter_redacts_common_secret_patterns_from_messages() -> None:
    output = StringIO()
    logger = logging.getLogger("portwatch.test.redaction")
    logger.handlers = [_handler(output)]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info('failed: Bearer header-secret token=query-secret {"token":"json-secret"}')

    rendered = output.getvalue()
    assert "header-secret" not in rendered
    assert "query-secret" not in rendered
    assert "json-secret" not in rendered
    assert rendered.count("[REDACTED]") == 3


def test_configure_logging_is_idempotent_and_updates_level() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("INFO")
        configure_logging("DEBUG")

        portwatch_handlers = [
            handler for handler in root.handlers if isinstance(handler.formatter, JsonFormatter)
        ]
        assert len(portwatch_handlers) == 1
        assert root.level == logging.DEBUG
        assert portwatch_handlers[0].level == logging.DEBUG
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


async def test_request_id_is_injected_into_logs_and_reset_after_request() -> None:
    output = StringIO()
    logger = logging.getLogger("portwatch.test.request")
    logger.handlers = [_handler(output)]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    app = FastAPI()
    app.middleware("http")(request_id_middleware)

    @app.get("/log")
    async def log_request(_request: Request) -> dict[str, bool]:
        logger.info("inside request")
        return {"ok": True}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/log", headers={"X-Request-Id": "request-123"})
    logger.info("outside request")

    inside, outside = [json.loads(line) for line in output.getvalue().splitlines()]
    assert response.headers["X-Request-Id"] == "request-123"
    assert inside["request_id"] == "request-123"
    assert "request_id" not in outside

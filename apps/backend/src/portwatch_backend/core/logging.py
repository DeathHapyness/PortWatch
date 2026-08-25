"""Structured JSON logging with request-scoped correlation.

The implementation deliberately uses the standard library only. Log records
contain a small, fixed schema instead of serializing every ``LogRecord``
attribute, which could accidentally expose request headers or other secrets.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("portwatch_request_id", default=None)
_HANDLER_MARKER = "_portwatch_json_handler"
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;\"]+"),
    re.compile(r"(?i)\b(api_?token|token)=([^\s,;]+)"),
    re.compile(r'(?i)("(?:api_?token|token)"\s*:\s*")[^"]*(")'),
)


def _redact_secrets(value: str) -> str:
    value = _SECRET_PATTERNS[0].sub("Bearer [REDACTED]", value)
    value = _SECRET_PATTERNS[1].sub(r"\1=[REDACTED]", value)
    return _SECRET_PATTERNS[2].sub(r"\1[REDACTED]\2", value)


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind a request ID to the current async context until its token is reset."""

    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


class JsonFormatter(logging.Formatter):
    """Render a LogRecord using PortWatch's stable, secret-minimizing schema."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_secrets(record.getMessage()),
        }
        request_id = _request_id.get()
        if request_id is not None:
            payload["request_id"] = request_id
        if record.exc_info is not None:
            payload["exception"] = _redact_secrets(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Install one reusable JSON handler on the process root logger."""

    normalized_level = level.upper()
    numeric_level = logging.getLevelNamesMapping().get(normalized_level)
    if numeric_level is None:
        raise ValueError(f"invalid log level: {level!r}")

    root = logging.getLogger()
    root.setLevel(numeric_level)

    for handler in root.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            handler.setLevel(numeric_level)
            handler.setFormatter(JsonFormatter())
            return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)

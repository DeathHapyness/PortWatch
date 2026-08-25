"""Runtime configuration.

All settings come from environment variables (12-factor). Nothing here reads
from a config file or database — see docs/adr/0002-no-database-v1.md for why.
"""

import math
from typing import Self
from urllib.parse import urlsplit

from pydantic import ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Hosts considered "local only" for the bind-security check below.
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTWATCH_", env_file=".env", extra="ignore")

    # Identity / meta
    environment: str = "development"
    log_level: str = "INFO"

    # Collector tuning
    collector_poll_interval_seconds: float = 30.0

    # Downstream dependencies (wired up from Phase 3 onward)
    docker_proxy_url: str = "http://docker-socket-proxy:2375"
    netprobe_url: str | None = None  # None => host-port scanning disabled

    # Port range PortWatch considers when computing "available" ports
    port_range_start: int = 1024
    port_range_end: int = 65535

    # Declared bind address — per ADR-0004, exposure beyond loopback is
    # opt-in and requires a token. This does NOT control what uvicorn
    # actually binds to (that's the separate `--host` CLI flag); it's the
    # operator's explicit declaration of intent, checked against api_token
    # below. Keep this in sync with the real `--host` value used to run the
    # server — same "cheap heuristic, not a hard guarantee" spirit as
    # infra/dev/guard.sh.
    bind_host: str = "127.0.0.1"

    # API auth — static bearer token, per ADR-0004. Empty string means auth is
    # disabled, which is only acceptable when bound to 127.0.0.1 — enforced
    # by validate_bind_security() below, not just documented.
    api_token: str = ""

    # CORS — restricted to the dashboard's own origin(s), never "*".
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    @field_validator("cors_allow_origins")
    @classmethod
    def _reject_cors_wildcard(cls, origins: list[str]) -> list[str]:
        if "*" in origins:
            raise ValueError(
                "PORTWATCH_CORS_ALLOW_ORIGINS may not contain '*' — CORS must be "
                "restricted to explicit dashboard origin(s), never a wildcard."
            )
        return origins

    @field_validator("collector_poll_interval_seconds")
    @classmethod
    def _validate_poll_interval(cls, interval: float) -> float:
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("collector_poll_interval_seconds must be finite and greater than zero")
        return interval

    @field_validator("port_range_start", "port_range_end")
    @classmethod
    def _validate_port(cls, port: int) -> int:
        if not 0 <= port <= 65535:
            raise ValueError("port range values must be between 0 and 65535")
        return port

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, level: str) -> str:
        normalized = level.upper()
        if normalized not in _LOG_LEVELS:
            supported = ", ".join(sorted(_LOG_LEVELS))
            raise ValueError(f"log_level must be one of: {supported}")
        return normalized

    @field_validator("docker_proxy_url", "netprobe_url")
    @classmethod
    def _validate_service_url(cls, url: str | None, info: ValidationInfo) -> str | None:
        if url is None:
            return None
        if url != url.strip() or any(character.isspace() for character in url):
            raise ValueError(f"{info.field_name} must not contain whitespace")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
            raise ValueError(f"{info.field_name} must be an absolute HTTP or HTTPS URL")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError(f"{info.field_name} contains an invalid port") from exc
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(f"{info.field_name} must not contain credentials")
        return url

    @field_validator("api_token")
    @classmethod
    def _reject_whitespace_only_token(cls, token: str) -> str:
        if token and not token.strip():
            raise ValueError("api_token must not contain only whitespace")
        return token

    @model_validator(mode="after")
    def _validate_port_range_order(self) -> Self:
        if self.port_range_start > self.port_range_end:
            raise ValueError("port_range_start must be less than or equal to port_range_end")
        return self


def validate_bind_security(settings: Settings) -> None:
    """Fail closed: refuse to run unauthenticated outside loopback.

    A non-loopback bind_host with no api_token means the API would be
    reachable from the LAN (or further) with zero authentication — exactly
    the scenario ADR-0004 says requires a token. This can't detect every
    possible misconfiguration (e.g. a reverse proxy exposing a loopback-bound
    server), but it catches the straightforward, common mistake.
    """

    if settings.bind_host not in _LOOPBACK_HOSTS and not settings.api_token:
        raise RuntimeError(
            f"PORTWATCH_BIND_HOST={settings.bind_host!r} is not loopback, but "
            "PORTWATCH_API_TOKEN is empty. Refusing to start without "
            "authentication when the API may be reachable off this machine "
            "— see docs/adr/0004-simple-static-token-auth.md. Set "
            "PORTWATCH_API_TOKEN or bind to 127.0.0.1."
        )


def get_settings() -> Settings:
    settings = Settings()
    validate_bind_security(settings)
    return settings

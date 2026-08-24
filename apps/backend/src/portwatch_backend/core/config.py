"""Runtime configuration.

All settings come from environment variables (12-factor). Nothing here reads
from a config file or database — see docs/adr/0002-no-database-v1.md for why.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # API auth — static bearer token, per ADR-0004. Empty string means auth is
    # disabled, which is only acceptable when bound to 127.0.0.1.
    api_token: str = ""

    # CORS — restricted to the dashboard's own origin(s), never "*".
    cors_allow_origins: list[str] = ["http://localhost:5173"]


def get_settings() -> Settings:
    return Settings()

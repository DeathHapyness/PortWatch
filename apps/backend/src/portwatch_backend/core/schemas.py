"""Shared domain models — the source of truth for the OpenAPI contract.

These are deliberately defined ahead of the real Collector (Phase 3) and API
logic (Phase 4) so the OpenAPI schema is stable early and the frontend can
build against it with a mock server. See docs/adr/0001.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ContainerStatus(StrEnum):
    running = "running"
    exited = "exited"
    paused = "paused"
    restarting = "restarting"
    dead = "dead"
    created = "created"


class PortProtocol(StrEnum):
    tcp = "tcp"
    udp = "udp"


class PortState(StrEnum):
    host = "host"  # occupied by a process on the host (via netprobe)
    published = "published"  # published by a Docker container
    free = "free"


class PublishedPort(BaseModel):
    container_port: int
    host_port: int | None = None
    host_ip: str | None = None
    protocol: PortProtocol = PortProtocol.tcp


class ContainerSummary(BaseModel):
    id: str = Field(description="Docker container ID (short form)")
    name: str
    image: str
    status: ContainerStatus
    health: str | None = Field(default=None, description="Docker healthcheck status, if any")
    created_at: datetime
    networks: list[str] = Field(default_factory=list)
    ports: list[PublishedPort] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class ContainerDetail(ContainerSummary):
    command: str | None = None
    env_redacted: list[str] = Field(
        default_factory=list,
        description="Env var KEYS only — values are never returned by the API",
    )
    mounts: list[str] = Field(default_factory=list)


class NetworkSummary(BaseModel):
    id: str
    name: str
    driver: str
    scope: str
    containers: list[str] = Field(default_factory=list, description="Connected container names")


class NetworkDetail(NetworkSummary):
    subnet: str | None = None
    gateway: str | None = None


class PortEntry(BaseModel):
    port: int
    protocol: PortProtocol
    state: PortState
    owner: str | None = Field(
        default=None, description="Container name (published) or process hint (host), if known"
    )


class PortsResponse(BaseModel):
    range_start: int
    range_end: int
    entries: list[PortEntry]


class SystemSummary(BaseModel):
    portwatch_status: str = "ok"
    docker_version: str | None = None
    docker_api_version: str | None = None
    containers_running: int = 0
    containers_stopped: int = 0
    networks_total: int = 0
    ports_used_total: int = 0
    ports_free_sample: int = 0
    host_ports_enabled: bool = False
    collector_last_poll: datetime | None = None


class ProblemDetail(BaseModel):
    """RFC 7807-shaped error payload — see docs/adr and the Observability
    section of the architecture blueprint."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    request_id: str | None = None

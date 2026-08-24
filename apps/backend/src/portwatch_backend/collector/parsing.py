"""Pure parsing helpers: raw docker-py dicts -> Pydantic domain models.

Deliberately free of any I/O or docker-py client calls so they can be unit-
tested against small fixture dicts without a real Docker daemon — the
roadmap calls this out explicitly as the Collector's "unit test (parsing)"
requirement, distinct from the integration test against the real dev
sandbox (see tests/collector/test_parsing.py vs test_service.py).
"""

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from portwatch_backend.collector.netprobe_client import HostPortEntry
from portwatch_backend.core.schemas import (
    ContainerDetail,
    ContainerStatus,
    ContainerSummary,
    NetworkSummary,
    PortEntry,
    PortProtocol,
    PortState,
    PublishedPort,
)

SHORT_ID_LENGTH = 12

# PW-03 (docs/audits/2026-08-23-auditoria-tecnica.md): Docker labels can carry
# internal domains, proxy/middleware rules and, in misconfigured stacks,
# credentials. Redact by *key* rather than trying to recognize secret-shaped
# values — cheaper, and it fails safe (a label that merely mentions one of
# these words but isn't actually sensitive is redacted too; that's an
# acceptable false positive for a monitoring surface).
_SENSITIVE_LABEL_KEY_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|access[_-]?key|private[_-]?key|auth)",
    re.IGNORECASE,
)
_REDACTED_LABEL_VALUE = "[redacted]"

# docker-py's `.attrs` is an untyped JSON blob straight off the Engine API —
# there's no stronger static shape to give it than this.
JSONDict = dict[str, Any]

# Docker Engine API timestamps are RFC 3339 with 0-9 fractional digits
# (commonly nanoseconds), e.g. "2026-08-23T22:00:00.123456789Z". stdlib
# datetime.fromisoformat only accepts 0, 3 or 6 fractional digits, so we
# parse with a regex and pad/truncate the fraction to exactly 6 (microsecond)
# digits ourselves rather than depend on fromisoformat's stricter grammar.
_TIMESTAMP_RE = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?"
    r"(?P<offset>Z|[+-]\d{2}:\d{2})?$"
)


def parse_docker_timestamp(raw: str) -> datetime:
    """Parse a Docker Engine API timestamp into an aware datetime (UTC or
    whatever offset the daemon reported — Docker always reports UTC "Z" in
    practice, but we honor an explicit offset if one is ever present)."""

    match = _TIMESTAMP_RE.match(raw.strip())
    if not match:
        raise ValueError(f"not a recognizable Docker timestamp: {raw!r}")

    base = match.group("base")
    fraction = (match.group("fraction") or "").ljust(6, "0")[:6]
    offset = match.group("offset") or "Z"
    if offset == "Z":
        offset = "+00:00"
    return datetime.fromisoformat(f"{base}.{fraction}{offset}")


def _redact_labels(labels: JSONDict) -> dict[str, str]:
    """Keep every label key (useful for filtering/observability) but mask
    the value of any key that looks credential-shaped. See PW-03 above."""

    return {
        key: (_REDACTED_LABEL_VALUE if _SENSITIVE_LABEL_KEY_RE.search(key) else value)
        for key, value in labels.items()
    }


def _format_command(config: JSONDict) -> str | None:
    """Entrypoint + Cmd, the same way `docker inspect` shows the effective
    command actually exec'd in the container — Cmd alone is misleading for
    images that rely on an ENTRYPOINT wrapper script."""

    entrypoint = config.get("Entrypoint") or []
    cmd = config.get("Cmd") or []
    parts = [
        *([entrypoint] if isinstance(entrypoint, str) else entrypoint),
        *([cmd] if isinstance(cmd, str) else cmd),
    ]
    return " ".join(parts) if parts else None


def _extract_env_keys(config: JSONDict) -> list[str]:
    """`Config.Env` entries are "KEY=value" — we only ever return the KEY.
    Values are never captured, let alone returned by the API (see
    ContainerDetail.env_redacted's docstring)."""

    keys = []
    for entry in config.get("Env") or []:
        key, sep, _value = entry.partition("=")
        if sep:
            keys.append(key)
    return sorted(keys)


def _format_mounts(attrs: JSONDict) -> list[str]:
    """Type + destination only — never the host Source path (PW-03: a bind
    mount's source can reveal host filesystem layout)."""

    formatted = []
    for mount in attrs.get("Mounts") or []:
        mount_type = mount.get("Type", "unknown")
        destination = mount.get("Destination")
        formatted.append(f"{mount_type}:{destination}" if destination else mount_type)
    return formatted


def parse_container_detail(attrs: JSONDict) -> ContainerDetail:
    """Build a ContainerDetail from one container's full inspect payload —
    docker-py `Container.attrs` *after* `.reload()`, i.e. the shape of
    `GET /containers/{id}/json`, not the leaner list-endpoint shape (which
    lacks Config.Labels, State.Health and a Networks map in some API
    versions). See collector/service.py for why we reload() before parsing.

    Returns the full detail shape (not just the summary-level fields) so the
    snapshot the Collector publishes is already API-response-ready — see
    collector/state.py and api/containers.py.
    """

    state = attrs.get("State") or {}
    config = attrs.get("Config") or {}
    network_settings = attrs.get("NetworkSettings") or {}

    health = None
    health_block = state.get("Health")
    if isinstance(health_block, dict):
        health = health_block.get("Status")

    networks = sorted((network_settings.get("Networks") or {}).keys())
    ports = _parse_published_ports(network_settings.get("Ports") or {})

    return ContainerDetail(
        id=attrs["Id"][:SHORT_ID_LENGTH],
        name=attrs["Name"].lstrip("/"),
        image=config.get("Image", ""),
        status=ContainerStatus(state.get("Status", "created")),
        health=health,
        created_at=parse_docker_timestamp(attrs["Created"]),
        networks=networks,
        ports=ports,
        labels=_redact_labels(config.get("Labels") or {}),
        command=_format_command(config),
        env_redacted=_extract_env_keys(config),
        mounts=_format_mounts(attrs),
    )


def _parse_published_ports(raw_ports: JSONDict) -> list[PublishedPort]:
    """`NetworkSettings.Ports` from a container inspect: a map of
    "<container_port>/<protocol>" -> list of host bindings, or None/empty if
    that container port is exposed but never published to the host."""

    published: list[PublishedPort] = []
    for key, bindings in raw_ports.items():
        if not bindings:
            continue
        container_port_text, _, protocol_text = key.partition("/")
        try:
            container_port = int(container_port_text)
            protocol = PortProtocol(protocol_text or "tcp")
        except ValueError:
            continue
        for binding in bindings:
            host_port_text = binding.get("HostPort")
            try:
                host_port = int(host_port_text) if host_port_text else None
            except (TypeError, ValueError):
                # A malformed/unexpected-shaped HostPort from the Docker API
                # must not surface as host_port=None — that already means
                # "container port exposed but not published to the host"
                # (see this function's docstring), a different, legitimate
                # state. Drop just this one binding instead, so one bad
                # value doesn't cost the container its other, valid
                # bindings (contrast with the container_port/protocol
                # `continue` above, which drops the whole port entry
                # because there's nothing salvageable there).
                continue
            published.append(
                PublishedPort(
                    container_port=container_port,
                    host_port=host_port,
                    host_ip=binding.get("HostIp") or None,
                    protocol=protocol,
                )
            )
    return published


def parse_network_summary(attrs: JSONDict) -> NetworkSummary:
    """Build a NetworkSummary from one network's full inspect payload —
    docker-py `Network.attrs` *after* `.reload()`. Confirmed against a real
    daemon (not just the API docs): `GET /networks` (`.list()`) leaves
    `Containers` as null; only `GET /networks/{id}` (inspect) populates it,
    same asymmetry as containers — see collector/service.py."""

    containers = sorted(
        entry.get("Name", container_id)
        for container_id, entry in (attrs.get("Containers") or {}).items()
    )
    return NetworkSummary(
        id=attrs["Id"],
        name=attrs["Name"],
        driver=attrs.get("Driver", ""),
        scope=attrs.get("Scope", ""),
        containers=containers,
    )


def build_port_entries(
    containers: Sequence[ContainerSummary],
    host_ports: Sequence[HostPortEntry],
) -> tuple[PortEntry, ...]:
    """Merge published container ports and netprobe's host-occupied ports
    into one deduplicated, sorted view.

    Published ports take precedence: a port Docker publishes is reported as
    "published", with its owning container, even though netprobe's raw host
    scan will also see it (Docker's own proxying makes that host port
    genuinely LISTEN-ing at the kernel level). Only host-occupied ports NOT
    accounted for by a known published port are reported as "host" — with no
    owner, since netprobe has no notion of which process that is.
    """

    entries: dict[tuple[int, PortProtocol], PortEntry] = {}

    for container in containers:
        for published_port in container.ports:
            if published_port.host_port is None:
                continue
            key = (published_port.host_port, published_port.protocol)
            entries.setdefault(
                key,
                PortEntry(
                    port=published_port.host_port,
                    protocol=published_port.protocol,
                    state=PortState.published,
                    owner=container.name,
                ),
            )

    for host_port in host_ports:
        try:
            protocol = PortProtocol(host_port["protocol"])
            port = int(host_port["port"])
        except (KeyError, ValueError):
            continue
        key = (port, protocol)
        if key in entries:
            continue
        entries[key] = PortEntry(port=port, protocol=protocol, state=PortState.host, owner=None)

    return tuple(sorted(entries.values(), key=lambda entry: (entry.protocol, entry.port)))

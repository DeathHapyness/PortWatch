"""Pure parsing helpers: raw docker-py dicts -> Pydantic domain models.

Deliberately free of any I/O or docker-py client calls so they can be unit-
tested against small fixture dicts without a real Docker daemon — the
roadmap calls this out explicitly as the Collector's "unit test (parsing)"
requirement, distinct from the integration test against the real dev
sandbox (see tests/collector/test_parsing.py vs test_service.py).
"""

import re
from collections.abc import Mapping, Sequence
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


class DockerPayloadError(ValueError):
    """A Docker Engine response has an unexpected JSON shape.

    Messages deliberately identify only the invalid field, never its value:
    inspect payloads may contain secrets in labels or environment variables.
    """


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DockerPayloadError(f"Docker field {field} must be an object with string keys")
    return value


def _required_string(attrs: Mapping[str, Any], field: str) -> str:
    value = attrs.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DockerPayloadError(f"Docker field {field} must be a non-empty string")
    return value


def _optional_string(attrs: Mapping[str, Any], field: str, *, default: str = "") -> str:
    value = attrs.get(field, default)
    if not isinstance(value, str):
        raise DockerPayloadError(f"Docker field {field} must be a string")
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DockerPayloadError(f"Docker field {field} must be an array of strings")
    return value


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


def _redact_labels(labels: Mapping[str, Any]) -> dict[str, str]:
    """Keep every label key (useful for filtering/observability) but mask
    the value of any key that looks credential-shaped. See PW-03 above."""

    if not all(isinstance(value, str) for value in labels.values()):
        raise DockerPayloadError("Docker field Config.Labels must contain string values")
    return {
        key: (_REDACTED_LABEL_VALUE if _SENSITIVE_LABEL_KEY_RE.search(key) else value)
        for key, value in labels.items()
    }


def _format_command(config: Mapping[str, Any]) -> str | None:
    """Entrypoint + Cmd, the same way `docker inspect` shows the effective
    command actually exec'd in the container — Cmd alone is misleading for
    images that rely on an ENTRYPOINT wrapper script."""

    raw_entrypoint = config.get("Entrypoint")
    raw_cmd = config.get("Cmd")
    entrypoint = (
        [raw_entrypoint]
        if isinstance(raw_entrypoint, str)
        else _string_list(raw_entrypoint, "Config.Entrypoint")
    )
    cmd = [raw_cmd] if isinstance(raw_cmd, str) else _string_list(raw_cmd, "Config.Cmd")
    parts = [
        *entrypoint,
        *cmd,
    ]
    return " ".join(parts) if parts else None


def _extract_env_keys(config: Mapping[str, Any]) -> list[str]:
    """`Config.Env` entries are "KEY=value" — we only ever return the KEY.
    Values are never captured, let alone returned by the API (see
    ContainerDetail.env_redacted's docstring)."""

    keys = []
    for entry in _string_list(config.get("Env"), "Config.Env"):
        key, sep, _value = entry.partition("=")
        if sep:
            keys.append(key)
    return sorted(keys)


def _format_mounts(attrs: Mapping[str, Any]) -> list[str]:
    """Type + destination only — never the host Source path (PW-03: a bind
    mount's source can reveal host filesystem layout)."""

    formatted: list[str] = []
    mounts = attrs.get("Mounts")
    if mounts is None:
        return formatted
    if not isinstance(mounts, list):
        raise DockerPayloadError("Docker field Mounts must be an array")
    for index, raw_mount in enumerate(mounts):
        mount = _mapping(raw_mount, f"Mounts[{index}]")
        mount_type = _optional_string(mount, "Type", default="unknown")
        destination = mount.get("Destination")
        if destination is not None and not isinstance(destination, str):
            raise DockerPayloadError(f"Docker field Mounts[{index}].Destination must be a string")
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

    root = _mapping(attrs, "container response")
    container_id = _required_string(root, "Id")
    name = _required_string(root, "Name")
    created = _required_string(root, "Created")
    state = _mapping(root.get("State"), "State")
    config = _mapping(root.get("Config"), "Config")
    network_settings = _mapping(root.get("NetworkSettings"), "NetworkSettings")
    status = _required_string(state, "Status")
    image = _optional_string(config, "Image")

    health = None
    health_block = state.get("Health")
    if health_block is not None:
        health_attrs = _mapping(health_block, "State.Health")
        health_value = health_attrs.get("Status")
        if health_value is not None and not isinstance(health_value, str):
            raise DockerPayloadError("Docker field State.Health.Status must be a string")
        health = health_value

    networks_map = _mapping(network_settings.get("Networks") or {}, "NetworkSettings.Networks")
    for network_name, network_attrs in networks_map.items():
        _mapping(network_attrs, f"NetworkSettings.Networks.{network_name}")
    networks = sorted(networks_map)
    ports = _parse_published_ports(
        _mapping(network_settings.get("Ports") or {}, "NetworkSettings.Ports")
    )
    labels = _mapping(config.get("Labels") or {}, "Config.Labels")

    return ContainerDetail(
        id=container_id[:SHORT_ID_LENGTH],
        name=name.lstrip("/"),
        image=image,
        status=ContainerStatus(status),
        health=health,
        created_at=parse_docker_timestamp(created),
        networks=networks,
        ports=ports,
        labels=_redact_labels(labels),
        command=_format_command(config),
        env_redacted=_extract_env_keys(config),
        mounts=_format_mounts(attrs),
    )


def _parse_published_ports(raw_ports: Mapping[str, Any]) -> list[PublishedPort]:
    """`NetworkSettings.Ports` from a container inspect: a map of
    "<container_port>/<protocol>" -> list of host bindings, or None/empty if
    that container port is exposed but never published to the host."""

    published: list[PublishedPort] = []
    for key, bindings in raw_ports.items():
        if bindings is None or bindings == []:
            continue
        if not isinstance(bindings, list):
            raise DockerPayloadError(f"Docker port bindings for {key} must be an array or null")
        container_port_text, _, protocol_text = key.partition("/")
        try:
            container_port = int(container_port_text)
            protocol = PortProtocol(protocol_text or "tcp")
        except ValueError:
            continue
        for index, raw_binding in enumerate(bindings):
            binding = _mapping(raw_binding, f"NetworkSettings.Ports.{key}[{index}]")
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
            host_ip = binding.get("HostIp")
            if host_ip is not None and not isinstance(host_ip, str):
                raise DockerPayloadError(
                    f"Docker field NetworkSettings.Ports.{key}[{index}].HostIp must be a string"
                )
            published.append(
                PublishedPort(
                    container_port=container_port,
                    host_port=host_port,
                    host_ip=host_ip or None,
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

    root = _mapping(attrs, "network response")
    network_id = _required_string(root, "Id")
    name = _required_string(root, "Name")
    driver = _optional_string(root, "Driver")
    scope = _optional_string(root, "Scope")
    containers_map = _mapping(root.get("Containers") or {}, "Containers")
    containers = []
    for container_id, raw_entry in containers_map.items():
        entry = _mapping(raw_entry, f"Containers.{container_id}")
        container_name = entry.get("Name", container_id)
        if not isinstance(container_name, str) or not container_name:
            raise DockerPayloadError(
                f"Docker field Containers.{container_id}.Name must be a non-empty string"
            )
        containers.append(container_name)
    return NetworkSummary(
        id=network_id,
        name=name,
        driver=driver,
        scope=scope,
        containers=sorted(containers),
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

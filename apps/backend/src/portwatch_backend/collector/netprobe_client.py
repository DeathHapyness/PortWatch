"""Client for the optional netprobe sidecar (host-occupied ports).

netprobe is the only component allowed network_mode: host, and it has no
Docker socket access at all — see docs/adr/0003-docker-access-isolation.md
and infra/netprobe/README.md for its HTTP contract. It is optional: when
Settings.netprobe_url is None, the Collector simply skips host-port
scanning and reports host_ports_enabled=False, per core/config.py.
"""

import ipaddress
import json
from typing import Any, TypedDict

import httpx


class HostPortEntry(TypedDict):
    protocol: str  # "tcp" | "udp"
    family: str  # "ipv4" | "ipv6"
    address: str
    port: int


class NetprobeError(RuntimeError):
    """Raised when netprobe is configured but unreachable or returns garbage."""


MAX_NETPROBE_RESPONSE_BYTES = 1_048_576


def _read_bounded_response(response: httpx.Response) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise NetprobeError("netprobe returned an invalid Content-Length header") from exc
        if declared_size < 0 or declared_size > MAX_NETPROBE_RESPONSE_BYTES:
            raise NetprobeError("netprobe response exceeds the 1 MiB safety limit")

    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_NETPROBE_RESPONSE_BYTES:
            raise NetprobeError("netprobe response exceeds the 1 MiB safety limit")
    return bytes(body)


def _validate_host_port_entry(value: Any, *, index: int) -> HostPortEntry:
    if not isinstance(value, dict):
        raise NetprobeError(f"netprobe ports[{index}] must be an object")

    protocol = value.get("protocol")
    if protocol not in {"tcp", "udp"}:
        raise NetprobeError(f"netprobe ports[{index}].protocol must be 'tcp' or 'udp'")

    family = value.get("family")
    if family not in {"ipv4", "ipv6"}:
        raise NetprobeError(f"netprobe ports[{index}].family must be 'ipv4' or 'ipv6'")

    address = value.get("address")
    if not isinstance(address, str) or not address:
        raise NetprobeError(f"netprobe ports[{index}].address must be a non-empty string")
    try:
        parsed_address = ipaddress.ip_address(address)
    except ValueError as exc:
        raise NetprobeError(f"netprobe ports[{index}].address is not a valid IP address") from exc
    expected_version = 4 if family == "ipv4" else 6
    if parsed_address.version != expected_version:
        raise NetprobeError(f"netprobe ports[{index}].address does not match its declared family")

    port = value.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise NetprobeError(f"netprobe ports[{index}].port must be an integer from 0 to 65535")

    return HostPortEntry(
        protocol=protocol,
        family=family,
        address=address,
        port=port,
    )


def fetch_host_ports(netprobe_url: str, *, timeout: float = 5.0) -> list[HostPortEntry]:
    """Return the occupied host ports reported by netprobe right now.

    Raises NetprobeError on any network/HTTP/shape problem — the caller
    decides whether that should downgrade host_ports_enabled for this cycle
    rather than fail the whole collection (netprobe is optional).
    """

    url = f"{netprobe_url.rstrip('/')}/host-ports"
    try:
        # Streamed deliberately: a plain httpx.get() already reads the whole
        # body into memory before _read_bounded_response ever runs, which
        # would make the 1 MiB check a no-op against the actual download.
        # Streaming lets the loop below abort the connection mid-transfer.
        with httpx.stream("GET", url, timeout=timeout) as response:
            response.raise_for_status()
            body = _read_bounded_response(response)
        payload = json.loads(body)
    except httpx.HTTPError as exc:
        raise NetprobeError(f"netprobe request to {url} failed: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NetprobeError(f"netprobe response from {url} was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise NetprobeError("netprobe response root must be a JSON object")

    ports = payload.get("ports")
    if not isinstance(ports, list):
        raise NetprobeError(f"netprobe response from {url} is missing a 'ports' array")
    return [_validate_host_port_entry(entry, index=index) for index, entry in enumerate(ports)]

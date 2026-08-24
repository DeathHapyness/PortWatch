"""Client for the optional netprobe sidecar (host-occupied ports).

netprobe is the only component allowed network_mode: host, and it has no
Docker socket access at all — see docs/adr/0003-docker-access-isolation.md
and infra/netprobe/README.md for its HTTP contract. It is optional: when
Settings.netprobe_url is None, the Collector simply skips host-port
scanning and reports host_ports_enabled=False, per core/config.py.
"""

from typing import TypedDict

import httpx


class HostPortEntry(TypedDict):
    protocol: str  # "tcp" | "udp"
    family: str  # "ipv4" | "ipv6"
    address: str
    port: int


class NetprobeError(RuntimeError):
    """Raised when netprobe is configured but unreachable or returns garbage."""


def fetch_host_ports(netprobe_url: str, *, timeout: float = 5.0) -> list[HostPortEntry]:
    """Return the occupied host ports reported by netprobe right now.

    Raises NetprobeError on any network/HTTP/shape problem — the caller
    decides whether that should downgrade host_ports_enabled for this cycle
    rather than fail the whole collection (netprobe is optional).
    """

    url = f"{netprobe_url.rstrip('/')}/host-ports"
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise NetprobeError(f"netprobe request to {url} failed: {exc}") from exc
    except ValueError as exc:  # invalid JSON
        raise NetprobeError(f"netprobe response from {url} was not valid JSON: {exc}") from exc

    ports = payload.get("ports")
    if not isinstance(ports, list):
        raise NetprobeError(f"netprobe response from {url} is missing a 'ports' array")
    return ports

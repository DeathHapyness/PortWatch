#!/usr/bin/env python3
"""netprobe — minimal read-only HTTP service that reports host ports in use.

Single purpose, single endpoint, stdlib only (see README.md for why). Parses
/proc/net/{tcp,tcp6,udp,udp6} directly instead of shelling out to `ss`/`netstat`
(which may not even be installed in a minimal image, and would add exec
surface for no benefit).

This process is meant to run with `network_mode: host` so that the /proc/net/*
files it reads reflect the host's network namespace, not a container's own
isolated one — see infra/dev/docker-compose.dev.yml and docs/adr/0003.

It never touches the Docker socket and requires no capabilities beyond
reading world-readable /proc files and binding a port > 1024 on loopback.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from ipaddress import ip_address
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# /proc/net/{tcp,udp}{,6} table paths and the address family each one holds.
PROC_NET_TABLES = (
    ("tcp", "ipv4", "/proc/net/tcp"),
    ("tcp", "ipv6", "/proc/net/tcp6"),
    ("udp", "ipv4", "/proc/net/udp"),
    ("udp", "ipv6", "/proc/net/udp6"),
)

# TCP connection states (include/net/tcp_states.h). We only care about
# LISTEN for TCP — that's what "port occupied on the host" means for the
# purpose of picking a free port for a new service. Established/time-wait
# entries share the *local* port of an already-listening socket, or are
# ephemeral outbound ports that aren't relevant to "can I bind this port".
TCP_STATE_LISTEN = "0A"

# The service is loopback-only, but another local process must not be able to
# exhaust it with slow or idle connections. Keep both values deliberately
# small: every request only reads /proc and returns a compact JSON document.
CONNECTION_TIMEOUT_SECONDS = 5.0
MAX_CONCURRENT_REQUESTS = 32


class NetprobeReadError(RuntimeError):
    """Raised when a required kernel socket table cannot be read."""


def _decode_ipv4(hex_ip: str) -> str:
    raw = bytes.fromhex(hex_ip)
    # Kernel stores the address in host byte order in this file, which on
    # every real-world (little-endian) host means the printed bytes are
    # reversed relative to dotted-quad notation.
    return ".".join(str(b) for b in raw[::-1])


def _decode_ipv6(hex_ip: str) -> str:
    raw = bytes.fromhex(hex_ip)
    # Same little-endian-word quirk, but per 32-bit word (4 bytes each).
    words = [raw[i : i + 4][::-1] for i in range(0, 16, 4)]
    return socket.inet_ntop(socket.AF_INET6, b"".join(words))


def _parse_local_address(field: str, family: str) -> tuple[str, int]:
    ip_hex, port_hex = field.split(":")
    port = int(port_hex, 16)
    ip = _decode_ipv4(ip_hex) if family == "ipv4" else _decode_ipv6(ip_hex)
    return ip, port


def read_occupied_ports() -> list[dict]:
    """Return one entry per occupied (protocol, address, port) triple."""
    entries: list[dict] = []
    seen: set[tuple[str, str, int]] = set()

    for proto, family, path in PROC_NET_TABLES:
        try:
            with open(path, encoding="ascii") as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            # IPv6 disabled on this host, or an unexpected kernel config.
            continue
        except OSError as exc:
            raise NetprobeReadError(f"failed to read kernel socket table {path}") from exc

        for line in lines[1:]:  # skip header row
            fields = line.split()
            if len(fields) < 4:
                continue
            local_address, state = fields[1], fields[3]

            if proto == "tcp" and state != TCP_STATE_LISTEN:
                continue
            # UDP has no LISTEN state; any entry in the table is a bound
            # socket, which is exactly "occupied" for a protocol with no
            # connection setup.

            try:
                address, port = _parse_local_address(local_address, family)
            except ValueError:
                continue

            key = (proto, address, port)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {"protocol": proto, "family": family, "address": address, "port": port}
            )

    entries.sort(key=lambda e: (e["protocol"], e["port"], e["family"], e["address"]))
    return entries


class Handler(BaseHTTPRequestHandler):
    server_version = "netprobe/1.0"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(CONNECTION_TIMEOUT_SECONDS)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path == "/host-ports":
            try:
                ports = read_occupied_ports()
            except NetprobeReadError:
                self.log_error("failed to read host socket tables")
                self._send_json(503, {"error": "host port data unavailable"})
                return
            self._send_json(
                200,
                {
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "count": len(ports),
                    "ports": ports,
                    "tcp_listen_ports": sorted(
                        {p["port"] for p in ports if p["protocol"] == "tcp"}
                    ),
                    "udp_ports": sorted({p["port"] for p in ports if p["protocol"] == "udp"}),
                },
            )
        elif self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:  # quieter, structured-ish access log
        sys.stderr.write(
            "netprobe %s - %s\n" % (self.address_string(), fmt % args)
        )


class NetprobeHTTPServer(ThreadingHTTPServer):
    """Small bounded HTTP server for the loopback-only probe API."""

    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        max_workers: int = MAX_CONCURRENT_REQUESTS,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.address_family = (
            socket.AF_INET6 if ip_address(server_address[0]).version == 6 else socket.AF_INET
        )
        self._worker_slots = threading.BoundedSemaphore(max_workers)
        super().__init__(server_address, handler_class)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        # Never block the accept loop waiting for a worker: close excess
        # connections immediately so the process remains responsive for a
        # legitimate health check while under local connection pressure.
        if not self._worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._worker_slots.release()
            raise

    def process_request_thread(
        self, request: socket.socket, client_address: tuple[str, int]
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def _validate_loopback_host(raw: str) -> str:
    """Reject anything that isn't a loopback address.

    network_mode: host means the usual `ports:` Compose mapping doesn't
    apply — the process itself is the only thing standing between
    NETPROBE_HOST and being reachable from the LAN, so this has to fail
    closed rather than trust the value blindly (see infra/netprobe/README.md).
    """

    try:
        address = ip_address(raw)
    except ValueError as exc:
        raise ValueError("NETPROBE_HOST must be a loopback IP address") from exc
    if not address.is_loopback:
        raise ValueError("NETPROBE_HOST must be a loopback IP address")
    return raw


def _validate_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError("NETPROBE_PORT must be an integer from 1024 to 65535") from exc
    if not 1024 <= port <= 65535:
        raise ValueError("NETPROBE_PORT must be an integer from 1024 to 65535")
    return port


def main() -> None:
    try:
        host = _validate_loopback_host(os.environ.get("NETPROBE_HOST", "127.0.0.1"))
        port = _validate_port(os.environ.get("NETPROBE_PORT", "8088"))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    server = NetprobeHTTPServer((host, port), Handler)
    sys.stderr.write(f"netprobe listening on {host}:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

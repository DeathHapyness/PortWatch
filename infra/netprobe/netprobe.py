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
import time
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

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path == "/host-ports":
            ports = read_occupied_ports()
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


def main() -> None:
    host = os.environ.get("NETPROBE_HOST", "127.0.0.1")
    port = int(os.environ.get("NETPROBE_PORT", "8088"))
    server = ThreadingHTTPServer((host, port), Handler)
    sys.stderr.write(f"netprobe listening on {host}:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

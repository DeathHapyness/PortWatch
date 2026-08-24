"""Additional regressions for Docker published-port parsing."""

from typing import Any

import pytest

from portwatch_backend.collector.parsing import build_port_entries, parse_container_detail
from portwatch_backend.core.schemas import PortProtocol, PortState


def _inspect_with_ports(ports: dict[str, Any]) -> dict[str, Any]:
    return {
        "Id": "container-port-parser",
        "Name": "/fixture-parser",
        "Created": "2026-01-01T00:00:00Z",
        "State": {"Status": "running"},
        "Config": {"Image": "fixture:ports", "Labels": {}},
        "NetworkSettings": {"Networks": {}, "Ports": ports},
    }


@pytest.mark.parametrize(
    ("raw_ports", "expected"),
    [
        (
            {"8080": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]},
            [(8080, 8080, "0.0.0.0", PortProtocol.tcp)],
        ),
        (
            {
                "8443/tcp": [
                    {"HostIp": "::", "HostPort": "8443"},
                    {"HostIp": "127.0.0.1", "HostPort": "8443"},
                ]
            },
            [
                (8443, 8443, "::", PortProtocol.tcp),
                (8443, 8443, "127.0.0.1", PortProtocol.tcp),
            ],
        ),
        (
            {"5353/udp": [{"HostIp": "::1", "HostPort": "5353"}]},
            [(5353, 5353, "::1", PortProtocol.udp)],
        ),
    ],
)
def test_parse_container_detail_preserves_valid_binding_shapes(
    raw_ports: dict[str, Any], expected: list[tuple[int, int, str, PortProtocol]]
) -> None:
    detail = parse_container_detail(_inspect_with_ports(raw_ports))

    assert [
        (port.container_port, port.host_port, port.host_ip, port.protocol) for port in detail.ports
    ] == expected


def test_parse_container_detail_skips_unpublished_and_unknown_protocol_ports() -> None:
    detail = parse_container_detail(
        _inspect_with_ports(
            {
                "80/tcp": None,
                "443/tcp": [],
                "9000/sctp": [{"HostIp": "0.0.0.0", "HostPort": "9000"}],
            }
        )
    )

    assert detail.ports == []


def test_build_port_entries_ignores_published_bindings_without_host_port() -> None:
    detail = parse_container_detail(
        _inspect_with_ports({"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": ""}]})
    )

    entries = build_port_entries([detail], [])

    assert entries == ()


def test_parse_container_detail_accepts_port_zero_binding() -> None:
    detail = parse_container_detail(
        _inspect_with_ports({"1/tcp": [{"HostIp": "127.0.0.1", "HostPort": "0"}]})
    )

    entries = build_port_entries([detail], [])

    assert [(entry.port, entry.protocol, entry.state) for entry in entries] == [
        (0, PortProtocol.tcp, PortState.published)
    ]


def test_build_port_entries_does_not_mutate_input_sequences() -> None:
    detail = parse_container_detail(
        _inspect_with_ports({"8080/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]})
    )
    host_ports = ({"protocol": "udp", "port": 5353, "family": "ipv6", "address": "::1"},)

    entries = build_port_entries((detail,), host_ports)

    assert [(entry.port, entry.protocol, entry.state) for entry in entries] == [
        (8080, PortProtocol.tcp, PortState.published),
        (5353, PortProtocol.udp, PortState.host),
    ]
    assert host_ports == ({"protocol": "udp", "port": 5353, "family": "ipv6", "address": "::1"},)

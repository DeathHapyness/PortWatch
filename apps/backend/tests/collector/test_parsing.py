"""Unit tests for collector/parsing.py — pure functions, fixture dicts only,
no Docker daemon involved. Fixtures are modeled on real docker-py `.attrs`
payloads captured against this machine's dev sandbox (Docker 29.6.2, API
1.55), not guessed from documentation alone — see e.g. the exact
NetworkSettings.Ports/Networks shapes and the nanosecond-precision Created
timestamp.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from portwatch_backend.collector.parsing import (
    build_port_entries,
    parse_container_summary,
    parse_docker_timestamp,
    parse_network_summary,
)
from portwatch_backend.core.schemas import (
    ContainerStatus,
    PortProtocol,
    PortState,
)

# --- parse_docker_timestamp -------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "2026-08-24T03:12:26.945003902Z",
            datetime(2026, 8, 24, 3, 12, 26, 945003, tzinfo=UTC),
        ),
        ("2026-08-24T03:12:26Z", datetime(2026, 8, 24, 3, 12, 26, 0, tzinfo=UTC)),
        (
            "2026-08-24T03:12:26.123Z",
            datetime(2026, 8, 24, 3, 12, 26, 123000, tzinfo=UTC),
        ),
        (
            "2026-08-24T03:12:26.123456+02:00",
            datetime(2026, 8, 24, 3, 12, 26, 123456, tzinfo=timezone(timedelta(hours=2))),
        ),
    ],
)
def test_parse_docker_timestamp_accepts_docker_engine_formats(raw: str, expected: datetime) -> None:
    parsed = parse_docker_timestamp(raw)
    assert parsed == expected
    assert parsed.tzinfo is not None


def test_parse_docker_timestamp_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="not a recognizable Docker timestamp"):
        parse_docker_timestamp("not-a-timestamp")


# --- parse_container_summary -------------------------------------------------

FIXTURE_WEB_ATTRS = {
    "Id": "b2e424a964a8619c55df90ce9b22ac5c7e5b7c2a9f7a30af93ea0e98fff74784",
    "Name": "/portwatch-dev-fixture-web",
    "Created": "2026-08-24T03:12:26.945003902Z",
    "State": {
        "Status": "running",
        "Running": True,
        "Paused": False,
        "Restarting": False,
        "OOMKilled": False,
        "Dead": False,
    },
    "Config": {
        "Image": "nginx:alpine",
        "Labels": {
            "portwatch.env": "dev-sandbox",
            "com.docker.compose.service": "fixture-web",
        },
    },
    "NetworkSettings": {
        "Networks": {"portwatch-dev-net": {"IPAddress": "172.18.0.3"}},
        "Ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8081"}]},
    },
}


def test_parse_container_summary_from_real_shaped_inspect() -> None:
    summary = parse_container_summary(FIXTURE_WEB_ATTRS)

    assert summary.id == "b2e424a964a8"  # truncated to short form
    assert summary.name == "portwatch-dev-fixture-web"  # leading slash stripped
    assert summary.image == "nginx:alpine"
    assert summary.status == ContainerStatus.running
    assert summary.health is None
    assert summary.networks == ["portwatch-dev-net"]
    assert summary.labels["portwatch.env"] == "dev-sandbox"
    assert len(summary.ports) == 1
    port = summary.ports[0]
    assert (port.container_port, port.host_port, port.host_ip, port.protocol) == (
        80,
        8081,
        "127.0.0.1",
        PortProtocol.tcp,
    )


def test_parse_container_summary_reads_health_status_when_present() -> None:
    attrs = {
        **FIXTURE_WEB_ATTRS,
        "State": {**FIXTURE_WEB_ATTRS["State"], "Health": {"Status": "healthy"}},
    }
    assert parse_container_summary(attrs).health == "healthy"


def test_parse_container_summary_ignores_exposed_but_unpublished_ports() -> None:
    attrs = {
        **FIXTURE_WEB_ATTRS,
        "NetworkSettings": {
            "Networks": {"portwatch-dev-net": {}},
            # 443/tcp exposed but never published (null bindings) — common
            # for e.g. an image that EXPOSEs a port the compose file never
            # publishes with `-p`/`ports:`.
            "Ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8081"}], "443/tcp": None},
        },
    }
    summary = parse_container_summary(attrs)
    assert [p.container_port for p in summary.ports] == [80]


def test_parse_container_summary_handles_multiple_host_bindings_per_port() -> None:
    # e.g. bound on both an IPv4 and an IPv6 host address.
    attrs = {
        **FIXTURE_WEB_ATTRS,
        "NetworkSettings": {
            "Networks": {"portwatch-dev-net": {}},
            "Ports": {
                "80/tcp": [
                    {"HostIp": "127.0.0.1", "HostPort": "8081"},
                    {"HostIp": "::1", "HostPort": "8081"},
                ]
            },
        },
    }
    summary = parse_container_summary(attrs)
    assert len(summary.ports) == 2
    assert {p.host_ip for p in summary.ports} == {"127.0.0.1", "::1"}


def test_parse_container_summary_rejects_unknown_status() -> None:
    attrs = {**FIXTURE_WEB_ATTRS, "State": {"Status": "some-future-docker-status"}}
    with pytest.raises(ValueError):
        parse_container_summary(attrs)


# --- parse_network_summary ---------------------------------------------------

NETWORK_ATTRS = {
    "Id": "7682254efc68e6df3b3e26be5f7e88ec2f9c00abf7e1c66eb0b4e1e6c1c0a111",
    "Name": "portwatch-dev-net",
    "Driver": "bridge",
    "Scope": "local",
    "Containers": {
        "b2e424a964a8619c55df90ce9b22ac5c7e5b7c2a9f7a30af93ea0e98fff74784": {
            "Name": "portwatch-dev-fixture-web",
            "IPv4Address": "172.18.0.3/16",
        },
        "ed8e0b452246868daa2d23ad13539e888103a0f1c344e73de00e3fa37487647": {
            "Name": "portwatch-dev-docker-socket-proxy",
            "IPv4Address": "172.18.0.2/16",
        },
    },
}


def test_parse_network_summary_lists_connected_container_names_sorted() -> None:
    summary = parse_network_summary(NETWORK_ATTRS)
    assert summary.id == NETWORK_ATTRS["Id"]
    assert summary.name == "portwatch-dev-net"
    assert summary.driver == "bridge"
    assert summary.containers == [
        "portwatch-dev-docker-socket-proxy",
        "portwatch-dev-fixture-web",
    ]


def test_parse_network_summary_handles_null_containers_map() -> None:
    # This is what client.networks.list() actually returns before reload() —
    # confirmed against a real daemon, not just documentation. A network with
    # no reload() yet (or a genuinely empty one) must not crash the parser.
    attrs = {**NETWORK_ATTRS, "Containers": None}
    assert parse_network_summary(attrs).containers == []


# --- build_port_entries -------------------------------------------------------


def test_build_port_entries_published_takes_precedence_over_host_scan() -> None:
    from portwatch_backend.core.schemas import ContainerSummary, PublishedPort

    container = ContainerSummary(
        id="abc123",
        name="fixture-web",
        image="nginx:alpine",
        status=ContainerStatus.running,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ports=[PublishedPort(container_port=80, host_port=8081, protocol=PortProtocol.tcp)],
    )
    # netprobe's raw scan sees the same host port (Docker's own proxying
    # makes it genuinely LISTEN-ing) plus one port nothing else knows about.
    host_ports = [
        {"protocol": "tcp", "port": 8081, "family": "ipv4", "address": "127.0.0.1"},
        {"protocol": "tcp", "port": 22, "family": "ipv4", "address": "0.0.0.0"},
    ]

    entries = build_port_entries([container], host_ports)

    by_port = {(e.port, e.protocol): e for e in entries}
    assert by_port[(8081, PortProtocol.tcp)].state == PortState.published
    assert by_port[(8081, PortProtocol.tcp)].owner == "fixture-web"
    assert by_port[(22, PortProtocol.tcp)].state == PortState.host
    assert by_port[(22, PortProtocol.tcp)].owner is None


def test_build_port_entries_sorted_and_deduplicated() -> None:
    host_ports = [
        {"protocol": "tcp", "port": 22, "family": "ipv4", "address": "0.0.0.0"},
        {"protocol": "tcp", "port": 22, "family": "ipv6", "address": "::"},
        {"protocol": "udp", "port": 53, "family": "ipv4", "address": "0.0.0.0"},
    ]
    entries = build_port_entries([], host_ports)
    assert [(e.port, e.protocol) for e in entries] == [
        (22, PortProtocol.tcp),
        (53, PortProtocol.udp),
    ]


def test_build_port_entries_ignores_malformed_host_port_entries() -> None:
    entries = build_port_entries([], [{"protocol": "not-a-protocol", "port": 1}, {}])
    assert entries == ()

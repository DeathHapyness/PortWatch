"""DockerPayloadError paths added to collector/parsing.py and the
_parse_version_info hardening in collector/service.py — a compromised or
buggy docker-socket-proxy must not crash the Collector or silently produce
garbage ContainerDetail/NetworkSummary/version fields (PW-06: the proxy
limits *mutation*, not response integrity).

Uses copy.deepcopy(FIXTURE_CONTAINER_ATTRS) (a local, real-shaped fixture —
this test tree has no package __init__.py files, so importing fixtures
across test modules isn't reliable; see tests/e2e/conftest.py's note on the
same issue) so each test starts from an already-valid payload and corrupts
exactly one field — narrower and less brittle than hand-building minimal
payloads for every case.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from portwatch_backend.collector.parsing import (
    DockerPayloadError,
    parse_container_detail,
    parse_network_summary,
)
from portwatch_backend.collector.service import _parse_version_info

FIXTURE_CONTAINER_ATTRS: dict[str, Any] = {
    "Id": "b2e424a964a8619c55df90ce9b22ac5c7e5b7c2a9f7a30af93ea0e98fff74784",
    "Name": "/portwatch-dev-fixture-web",
    "Created": "2026-08-24T03:12:26.945003902Z",
    "State": {"Status": "running"},
    "Config": {
        "Image": "nginx:alpine",
        "Labels": {"portwatch.env": "dev-sandbox"},
        "Entrypoint": ["/docker-entrypoint.sh"],
        "Cmd": ["nginx", "-g", "daemon off;"],
        "Env": ["NGINX_VERSION=1.27.0"],
    },
    "NetworkSettings": {
        "Networks": {"portwatch-dev-net": {"IPAddress": "172.18.0.3"}},
        "Ports": {"80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8081"}]},
    },
    "Mounts": [
        {"Type": "bind", "Source": "/host/conf", "Destination": "/etc/nginx/conf.d", "RW": False},
    ],
}


def _container(**overrides: Any) -> dict[str, Any]:
    attrs = copy.deepcopy(FIXTURE_CONTAINER_ATTRS)
    attrs.update(overrides)
    return attrs


NETWORK_ATTRS: dict[str, Any] = {
    "Id": "net-id-0123456789ab",
    "Name": "portwatch-dev-net",
    "Driver": "bridge",
    "Scope": "local",
    "Containers": {
        "container-id": {"Name": "portwatch-dev-fixture-web"},
    },
}


def _network(**overrides: Any) -> dict[str, Any]:
    attrs = copy.deepcopy(NETWORK_ATTRS)
    attrs.update(overrides)
    return attrs


# --- parse_container_detail ------------------------------------------------


@pytest.mark.parametrize("root", [[], "oops", 42, None])
def test_parse_container_detail_rejects_a_non_object_root(root: object) -> None:
    with pytest.raises(DockerPayloadError, match="container response"):
        parse_container_detail(root)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["Id", "Name", "Created"])
def test_parse_container_detail_rejects_a_missing_required_string(field: str) -> None:
    attrs = _container()
    del attrs[field]
    with pytest.raises(DockerPayloadError, match=field):
        parse_container_detail(attrs)


@pytest.mark.parametrize("section", ["State", "Config", "NetworkSettings"])
def test_parse_container_detail_rejects_a_non_object_section(section: str) -> None:
    # These sections are always present on a real Docker inspect response —
    # this is the hardening path (a compromised/buggy proxy), not a real
    # shape Docker itself would ever return.
    attrs = _container(**{section: "not-an-object"})
    with pytest.raises(DockerPayloadError, match=section):
        parse_container_detail(attrs)


def test_parse_container_detail_now_requires_state_status() -> None:
    # Behavior change from the pre-hardening code: State.Status used to
    # default to "created" when absent. Docker always sends it in practice,
    # so requiring it closes a silent-guess path rather than losing any
    # real-world coverage.
    attrs = _container()
    del attrs["State"]["Status"]
    with pytest.raises(DockerPayloadError, match="Status"):
        parse_container_detail(attrs)


def test_parse_container_detail_rejects_a_non_string_label_value() -> None:
    attrs = _container()
    attrs["Config"]["Labels"]["weird"] = 123
    with pytest.raises(DockerPayloadError, match="Config.Labels"):
        parse_container_detail(attrs)


def test_parse_container_detail_rejects_a_non_list_mounts() -> None:
    attrs = _container(Mounts="not-a-list")
    with pytest.raises(DockerPayloadError, match="Mounts"):
        parse_container_detail(attrs)


def test_parse_container_detail_rejects_a_non_object_mount_entry() -> None:
    attrs = _container(Mounts=["not-an-object"])
    with pytest.raises(DockerPayloadError, match=r"Mounts\[0\]"):
        parse_container_detail(attrs)


def test_parse_container_detail_rejects_a_non_list_port_bindings() -> None:
    attrs = _container()
    attrs["NetworkSettings"]["Ports"]["80/tcp"] = "not-a-list"
    with pytest.raises(DockerPayloadError, match="80/tcp"):
        parse_container_detail(attrs)


def test_parse_container_detail_rejects_a_non_object_port_binding() -> None:
    attrs = _container()
    attrs["NetworkSettings"]["Ports"]["80/tcp"] = ["not-an-object"]
    with pytest.raises(DockerPayloadError, match=r"80/tcp\[0\]"):
        parse_container_detail(attrs)


def test_parse_container_detail_rejects_a_non_string_host_ip() -> None:
    attrs = _container()
    attrs["NetworkSettings"]["Ports"]["80/tcp"] = [{"HostIp": 123, "HostPort": "8081"}]
    with pytest.raises(DockerPayloadError, match="HostIp"):
        parse_container_detail(attrs)


def test_parse_container_detail_still_accepts_the_real_shaped_fixture() -> None:
    # Regression guard: none of the new validation should reject the
    # already-valid fixture every other test in this module corrupts.
    detail = parse_container_detail(_container())
    assert detail.status.value == "running"


# --- parse_network_summary --------------------------------------------------


@pytest.mark.parametrize("root", [[], "oops", 42, None])
def test_parse_network_summary_rejects_a_non_object_root(root: object) -> None:
    with pytest.raises(DockerPayloadError, match="network response"):
        parse_network_summary(root)  # type: ignore[arg-type]


def test_parse_network_summary_rejects_a_non_object_containers_entry() -> None:
    attrs = _network(Containers={"container-id": "not-an-object"})
    with pytest.raises(DockerPayloadError, match="Containers.container-id"):
        parse_network_summary(attrs)


def test_parse_network_summary_rejects_an_empty_container_name() -> None:
    attrs = _network(Containers={"container-id": {"Name": ""}})
    with pytest.raises(DockerPayloadError, match="Containers.container-id.Name"):
        parse_network_summary(attrs)


def test_parse_network_summary_still_accepts_the_valid_fixture() -> None:
    summary = parse_network_summary(_network())
    assert summary.containers == ["portwatch-dev-fixture-web"]


# --- service._parse_version_info --------------------------------------------


@pytest.mark.parametrize("payload", [[], "oops", 42, None])
def test_parse_version_info_rejects_a_non_object_payload(payload: object) -> None:
    with pytest.raises(RuntimeError, match="Docker /version response"):
        _parse_version_info(payload)


def test_parse_version_info_allows_missing_fields_as_none() -> None:
    assert _parse_version_info({}) == (None, None)


def test_parse_version_info_rejects_a_non_string_field() -> None:
    with pytest.raises(RuntimeError, match="Version"):
        _parse_version_info({"Version": 123})


def test_parse_version_info_rejects_an_empty_string_field() -> None:
    with pytest.raises(RuntimeError, match="ApiVersion"):
        _parse_version_info({"ApiVersion": "   "})


def test_parse_version_info_accepts_the_real_shape() -> None:
    assert _parse_version_info({"Version": "29.6.2", "ApiVersion": "1.55"}) == (
        "29.6.2",
        "1.55",
    )

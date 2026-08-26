"""fetch_host_ports (collector/netprobe_client.py) — HTTP, JSON-shape and
per-entry validation. httpx.stream is monkeypatched directly (the module
calls it as a bare module-level function, not through an injectable
client), so there's no need for a real server or transport. A stubbed
httpx.Response is fully in-memory regardless of how it was obtained, so
.iter_bytes() on it behaves the same whether or not the real code streams —
these fakes only need to satisfy the `with httpx.stream(...) as response:`
context-manager protocol.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from portwatch_backend.collector import netprobe_client
from portwatch_backend.collector.netprobe_client import NetprobeError, fetch_host_ports

NETPROBE_URL = "http://127.0.0.1:8088"
VALID_ENTRY: dict[str, Any] = {
    "protocol": "tcp",
    "family": "ipv4",
    "address": "127.0.0.1",
    "port": 8080,
}


class _FakeStreamContext:
    """Stands in for httpx.stream(...)'s context manager in tests."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def __enter__(self) -> httpx.Response:
        return self._response

    def __exit__(self, *exc_info: object) -> None:
        return None


def _stub_response(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    # raise_for_status() requires a `request` to be attached, even for a 2xx
    # response that will never actually raise — httpx errors out with a
    # RuntimeError otherwise ("request instance has not been set").
    response._request = httpx.Request("GET", f"{NETPROBE_URL}/host-ports")
    monkeypatch.setattr(
        netprobe_client.httpx,
        "stream",
        lambda *args, **kwargs: _FakeStreamContext(response),
    )


def _stub_get_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def _raise(*args: object, **kwargs: object) -> _FakeStreamContext:
        raise exc

    monkeypatch.setattr(netprobe_client.httpx, "stream", _raise)


def test_fetch_host_ports_parses_a_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [VALID_ENTRY]}))

    assert fetch_host_ports(NETPROBE_URL) == [VALID_ENTRY]


def test_fetch_host_ports_accepts_a_matching_ipv6_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = {"protocol": "udp", "family": "ipv6", "address": "::", "port": 68}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [entry]}))

    assert fetch_host_ports(NETPROBE_URL) == [entry]


def test_fetch_host_ports_accepts_zero_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": []}))

    assert fetch_host_ports(NETPROBE_URL) == []


def test_fetch_host_ports_raises_on_a_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_get_raises(monkeypatch, httpx.ConnectError("connection refused"))

    with pytest.raises(NetprobeError, match="request to"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_raises_on_a_non_2xx_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_response(monkeypatch, httpx.Response(500, text="boom"))

    with pytest.raises(NetprobeError, match="request to"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_response(monkeypatch, httpx.Response(200, text="not-json"))

    with pytest.raises(NetprobeError, match="not valid JSON"):
        fetch_host_ports(NETPROBE_URL)


@pytest.mark.parametrize("payload", [[], "oops", 42])
def test_fetch_host_ports_rejects_a_non_object_response_root(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    _stub_response(monkeypatch, httpx.Response(200, json=payload))

    with pytest.raises(NetprobeError, match="root must be a JSON object"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_rejects_a_json_null_response_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # httpx.Response(json=None) means "no JSON body", not "encode a literal
    # null" — text="null" is the only way to put an actual JSON null on the
    # wire, which is the case this test (as opposed to the parametrized one
    # above) is actually targeting.
    _stub_response(monkeypatch, httpx.Response(200, text="null"))

    with pytest.raises(NetprobeError, match="root must be a JSON object"):
        fetch_host_ports(NETPROBE_URL)


@pytest.mark.parametrize("ports", [None, "oops", {}, 42])
def test_fetch_host_ports_rejects_a_ports_field_that_is_not_a_list(
    monkeypatch: pytest.MonkeyPatch, ports: object
) -> None:
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": ports}))

    with pytest.raises(NetprobeError, match="missing a 'ports' array"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_rejects_an_entry_that_is_not_an_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": ["not-an-object"]}))

    with pytest.raises(NetprobeError, match=r"ports\[0\] must be an object"):
        fetch_host_ports(NETPROBE_URL)


@pytest.mark.parametrize("protocol", ["sctp", "TCP", "", None, 6])
def test_fetch_host_ports_rejects_an_invalid_protocol(
    monkeypatch: pytest.MonkeyPatch, protocol: object
) -> None:
    entry = {**VALID_ENTRY, "protocol": protocol}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [entry]}))

    with pytest.raises(NetprobeError, match="protocol must be"):
        fetch_host_ports(NETPROBE_URL)


@pytest.mark.parametrize("family", ["ipv5", "IPV4", "", None])
def test_fetch_host_ports_rejects_an_invalid_family(
    monkeypatch: pytest.MonkeyPatch, family: object
) -> None:
    entry = {**VALID_ENTRY, "family": family}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [entry]}))

    with pytest.raises(NetprobeError, match="family must be"):
        fetch_host_ports(NETPROBE_URL)


@pytest.mark.parametrize("address", ["", "not-an-ip", "999.999.999.999", None, 123])
def test_fetch_host_ports_rejects_an_invalid_address(
    monkeypatch: pytest.MonkeyPatch, address: object
) -> None:
    entry = {**VALID_ENTRY, "address": address}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [entry]}))

    with pytest.raises(NetprobeError):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_rejects_an_address_that_does_not_match_its_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A real, valid IPv4 address — just declared under the wrong family. The
    # cross-check must catch a mismatch, not just "is this parseable as
    # *some* IP".
    entry = {**VALID_ENTRY, "family": "ipv6", "address": "127.0.0.1"}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [entry]}))

    with pytest.raises(NetprobeError, match="does not match its declared family"):
        fetch_host_ports(NETPROBE_URL)


@pytest.mark.parametrize("port", [-1, 65536, "8080", True, None, 8080.0])
def test_fetch_host_ports_rejects_an_invalid_port(
    monkeypatch: pytest.MonkeyPatch, port: object
) -> None:
    entry = {**VALID_ENTRY, "port": port}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [entry]}))

    with pytest.raises(NetprobeError, match="port must be an integer"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_accepts_the_port_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [{**VALID_ENTRY, "port": 0}, {**VALID_ENTRY, "port": 65535}]
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": entries}))

    assert fetch_host_ports(NETPROBE_URL) == entries


def test_fetch_host_ports_reports_the_index_of_the_failing_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_entry = {**VALID_ENTRY, "port": "not-a-port"}
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [VALID_ENTRY, bad_entry]}))

    with pytest.raises(NetprobeError, match=r"ports\[1\]"):
        fetch_host_ports(NETPROBE_URL)


# --- response-size bound (core/netprobe_client.py's _read_bounded_response) --


def test_fetch_host_ports_rejects_a_declared_content_length_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        json={"ports": []},
        headers={"content-length": str(netprobe_client.MAX_NETPROBE_RESPONSE_BYTES + 1)},
    )
    _stub_response(monkeypatch, response)

    with pytest.raises(NetprobeError, match="exceeds the 1 MiB safety limit"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_rejects_a_negative_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(200, json={"ports": []}, headers={"content-length": "-1"})
    _stub_response(monkeypatch, response)

    with pytest.raises(NetprobeError, match="exceeds the 1 MiB safety limit"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_rejects_a_non_numeric_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(200, json={"ports": []}, headers={"content-length": "not-a-number"})
    _stub_response(monkeypatch, response)

    with pytest.raises(NetprobeError, match="invalid Content-Length"):
        fetch_host_ports(NETPROBE_URL)


def test_fetch_host_ports_accepts_a_response_within_the_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No content-length header at all — exercises the actual byte-counting
    # loop rather than the header pre-check.
    _stub_response(monkeypatch, httpx.Response(200, json={"ports": [VALID_ENTRY]}))

    assert fetch_host_ports(NETPROBE_URL) == [VALID_ENTRY]


def test_fetch_host_ports_aborts_an_oversized_stream_without_content_length() -> None:
    # A monkeypatched fake response can't demonstrate genuine mid-stream
    # abortion (it's always already fully in memory) — this spins up a real
    # HTTP server that streams well past the limit with no Content-Length
    # header (chunked/close-delimited), the scenario the header pre-check
    # alone can't catch. Also guards against a regression back to a plain
    # httpx.get(), which reads the whole body before any bound could apply
    # (verified manually: it did, before this fix switched to httpx.stream).
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    oversized_total = netprobe_client.MAX_NETPROBE_RESPONSE_BYTES * 4
    sent_before_disconnect: list[int] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            chunk = b"0" * 65536
            sent = 0
            try:
                while sent < oversized_total:
                    self.wfile.write(chunk)
                    sent += len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                sent_before_disconnect.append(sent)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(NetprobeError, match="exceeds the 1 MiB safety limit"):
            fetch_host_ports(f"http://127.0.0.1:{port}", timeout=5)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert sent_before_disconnect
    # The client must have given up well before the server finished
    # producing all `oversized_total` bytes — the actual point of streaming.
    assert sent_before_disconnect[0] < oversized_total

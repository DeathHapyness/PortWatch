from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

NETPROBE_PATH = Path(__file__).parents[1] / "netprobe.py"
SPEC = importlib.util.spec_from_file_location("portwatch_netprobe", NETPROBE_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import machinery guard
    raise RuntimeError(f"could not load netprobe module from {NETPROBE_PATH}")
netprobe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = netprobe
SPEC.loader.exec_module(netprobe)

PROC_HEADER = "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"


def proc_row(local_address: str, state: str) -> str:
    return f"0: {local_address} 00000000:0000 {state} 00000000:00000000 00:00000000 00000000 0 0 0\n"


class AddressParsingTests(unittest.TestCase):
    def test_decodes_ipv4_kernel_byte_order(self) -> None:
        self.assertEqual(
            netprobe._parse_local_address("0100007F:1F90", "ipv4"), ("127.0.0.1", 8080)
        )

    def test_decodes_ipv6_kernel_word_order(self) -> None:
        self.assertEqual(
            netprobe._parse_local_address(
                "00000000000000000000000001000000:01BB", "ipv6"
            ),
            ("::1", 443),
        )

    def test_rejects_invalid_address_fields(self) -> None:
        with self.assertRaises(ValueError):
            netprobe._parse_local_address("not-a-proc-address", "ipv4")


class StartupValidationTests(unittest.TestCase):
    """_validate_loopback_host / _validate_port — main()'s trust-boundary
    checks, factored out so they're testable without actually starting a
    server. network_mode: host means the process itself is the only thing
    that can stop NETPROBE_HOST from being reachable off the machine."""

    def test_accepts_ipv4_and_ipv6_loopback_hosts(self) -> None:
        self.assertEqual(netprobe._validate_loopback_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(netprobe._validate_loopback_host("::1"), "::1")

    def test_rejects_a_non_loopback_address(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a loopback IP address"):
            netprobe._validate_loopback_host("0.0.0.0")

    def test_rejects_a_lan_address(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a loopback IP address"):
            netprobe._validate_loopback_host("192.168.1.10")

    def test_rejects_a_value_that_is_not_an_ip_address(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a loopback IP address"):
            netprobe._validate_loopback_host("localhost")

    def test_accepts_the_port_boundaries(self) -> None:
        self.assertEqual(netprobe._validate_port("1024"), 1024)
        self.assertEqual(netprobe._validate_port("65535"), 65535)

    def test_rejects_a_port_below_1024(self) -> None:
        with self.assertRaisesRegex(ValueError, "1024 to 65535"):
            netprobe._validate_port("1023")

    def test_rejects_a_port_above_65535(self) -> None:
        with self.assertRaisesRegex(ValueError, "1024 to 65535"):
            netprobe._validate_port("65536")

    def test_rejects_a_non_numeric_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "1024 to 65535"):
            netprobe._validate_port("not-a-port")


class OccupiedPortsTests(unittest.TestCase):
    def test_reads_bound_ports_filters_tcp_states_and_deduplicates(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tables = {
                "tcp": PROC_HEADER
                + proc_row("00000000:0016", "0A")
                + proc_row("00000000:0016", "0A")
                + proc_row("0100007F:C350", "01"),
                "tcp6": PROC_HEADER
                + proc_row("00000000000000000000000000000000:01BB", "0A"),
                "udp": PROC_HEADER
                + proc_row("0100007F:14E9", "07")
                + "malformed row\n",
                "udp6": PROC_HEADER + proc_row("invalid:field", "07"),
            }
            paths: list[tuple[str, str, str]] = []
            for name, content in tables.items():
                path = root / name
                path.write_text(content, encoding="ascii")
                protocol = "tcp" if name.startswith("tcp") else "udp"
                family = "ipv6" if name.endswith("6") else "ipv4"
                paths.append((protocol, family, str(path)))

            with patch.object(netprobe, "PROC_NET_TABLES", tuple(paths)):
                entries = netprobe.read_occupied_ports()

        self.assertEqual(
            entries,
            [
                {"protocol": "tcp", "family": "ipv4", "address": "0.0.0.0", "port": 22},
                {"protocol": "tcp", "family": "ipv6", "address": "::", "port": 443},
                {
                    "protocol": "udp",
                    "family": "ipv4",
                    "address": "127.0.0.1",
                    "port": 5353,
                },
            ],
        )

    def test_skips_optional_proc_tables_that_do_not_exist(self) -> None:
        with patch.object(
            netprobe,
            "PROC_NET_TABLES",
            (("tcp", "ipv4", "/definitely/missing/portwatch-proc-table"),),
        ):
            self.assertEqual(netprobe.read_occupied_ports(), [])


class HttpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = netprobe.NetprobeHTTPServer(("127.0.0.1", 0), netprobe.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get_json(self, path: str) -> tuple[int, dict]:
        try:
            response = urllib.request.urlopen(f"{self.base_url}{path}", timeout=2)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_health_endpoint(self) -> None:
        self.assertEqual(self.get_json("/health"), (200, {"status": "ok"}))

    def test_unknown_route_is_json_404(self) -> None:
        self.assertEqual(self.get_json("/missing"), (404, {"error": "not found"}))

    def test_response_headers_prevent_caching_and_content_sniffing(self) -> None:
        response = urllib.request.urlopen(f"{self.base_url}/health", timeout=2)
        with response:
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")

    def test_a_kernel_read_failure_returns_503_without_leaking_details(self) -> None:
        with patch.object(
            netprobe,
            "read_occupied_ports",
            side_effect=netprobe.NetprobeReadError("failed to read kernel socket table /proc/net/oops"),
        ):
            status, payload = self.get_json("/host-ports")

        self.assertEqual(status, 503)
        self.assertEqual(payload, {"error": "host port data unavailable"})

    def test_host_ports_response_contains_sorted_protocol_summaries(self) -> None:
        ports = [
            {"protocol": "udp", "family": "ipv4", "address": "0.0.0.0", "port": 5353},
            {"protocol": "tcp", "family": "ipv6", "address": "::", "port": 8080},
            {"protocol": "tcp", "family": "ipv4", "address": "0.0.0.0", "port": 443},
            {"protocol": "tcp", "family": "ipv4", "address": "127.0.0.1", "port": 8080},
        ]
        with patch.object(netprobe, "read_occupied_ports", return_value=ports):
            status, payload = self.get_json("/host-ports")

        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 4)
        self.assertEqual(payload["ports"], ports)
        self.assertEqual(payload["tcp_listen_ports"], [443, 8080])
        self.assertEqual(payload["udp_ports"], [5353])
        self.assertRegex(
            payload["generated_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        )


class ServerHardeningTests(unittest.TestCase):
    def test_server_threads_are_daemonized_and_close_does_not_wait_for_handlers(self) -> None:
        self.assertIs(netprobe.NetprobeHTTPServer.daemon_threads, True)
        self.assertIs(netprobe.NetprobeHTTPServer.block_on_close, False)
        self.assertIs(netprobe.NetprobeHTTPServer.allow_reuse_address, True)

    def test_rejects_connections_when_all_worker_slots_are_busy(self) -> None:
        server = netprobe.NetprobeHTTPServer(
            ("127.0.0.1", 0), netprobe.Handler, max_workers=1
        )
        request = Mock(spec=socket.socket)
        self.assertTrue(server._worker_slots.acquire(blocking=False))
        try:
            with patch.object(server, "shutdown_request") as shutdown_request:
                server.process_request(request, ("127.0.0.1", 12345))
                shutdown_request.assert_called_once_with(request)
        finally:
            server._worker_slots.release()
            server.server_close()

    def test_rejects_invalid_worker_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_workers must be at least 1"):
            netprobe.NetprobeHTTPServer(
                ("127.0.0.1", 0), netprobe.Handler, max_workers=0
            )

    def test_binds_ipv6_loopback_when_configured(self) -> None:
        # NETPROBE_HOST=::1 is accepted by _validate_loopback_host, so the
        # server must actually be able to bind there — the stdlib
        # HTTPServer's hardcoded AF_INET default would fail this silently
        # otherwise (before this fix, ::1 was validated as loopback but the
        # server always tried to bind as IPv4).
        try:
            server = netprobe.NetprobeHTTPServer(("::1", 0), netprobe.Handler)
        except OSError as exc:  # pragma: no cover - only if the host lacks IPv6
            self.skipTest(f"IPv6 loopback unavailable in this environment: {exc}")
        try:
            self.assertEqual(server.address_family, socket.AF_INET6)
            self.assertEqual(server.server_address[0], "::1")
        finally:
            server.server_close()

    def test_binds_ipv4_loopback_by_default(self) -> None:
        server = netprobe.NetprobeHTTPServer(("127.0.0.1", 0), netprobe.Handler)
        try:
            self.assertEqual(server.address_family, socket.AF_INET)
        finally:
            server.server_close()

    def test_idle_connection_is_closed_after_timeout(self) -> None:
        with patch.object(netprobe, "CONNECTION_TIMEOUT_SECONDS", 0.05):
            server = netprobe.NetprobeHTTPServer(("127.0.0.1", 0), netprobe.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            client = socket.create_connection(server.server_address, timeout=1)
            client.settimeout(1)
            try:
                self.assertEqual(client.recv(1), b"")
            finally:
                client.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

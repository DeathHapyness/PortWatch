from __future__ import annotations

import importlib.util
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), netprobe.Handler)
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


if __name__ == "__main__":
    unittest.main()

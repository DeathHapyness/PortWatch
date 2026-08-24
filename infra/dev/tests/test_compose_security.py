"""Static security policy for the local development Compose stack.

The suite only renders Compose configuration; it never contacts a Docker
daemon, creates a container, or bypasses infra/dev/guard.sh.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPO_ROOT / "infra" / "dev" / "docker-compose.dev.yml"
SOCKET_PATH = "/var/run/docker.sock"
SANDBOX_LABEL = "portwatch.env"


class ComposeSecurityPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "config",
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.config: dict[str, Any] = json.loads(result.stdout)
        cls.services: dict[str, dict[str, Any]] = cls.config["services"]

    def test_every_service_and_network_has_the_sandbox_label(self) -> None:
        for name, service in self.services.items():
            with self.subTest(service=name):
                self.assertEqual(service.get("labels", {}).get(SANDBOX_LABEL), "dev-sandbox")

        for name, network in self.config["networks"].items():
            with self.subTest(network=name):
                self.assertEqual(network.get("labels", {}).get(SANDBOX_LABEL), "dev-sandbox")

    def test_only_socket_proxy_mounts_the_docker_socket_read_only(self) -> None:
        socket_mounts: list[tuple[str, dict[str, Any]]] = []
        for name, service in self.services.items():
            for volume in service.get("volumes", []):
                if volume.get("source") == SOCKET_PATH or volume.get("target") == SOCKET_PATH:
                    socket_mounts.append((name, volume))

        self.assertEqual(len(socket_mounts), 1)
        service_name, mount = socket_mounts[0]
        self.assertEqual(service_name, "docker-socket-proxy")
        self.assertEqual(mount.get("source"), SOCKET_PATH)
        self.assertEqual(mount.get("target"), SOCKET_PATH)
        self.assertIs(mount.get("read_only"), True)

    def test_only_netprobe_uses_host_network_without_volumes(self) -> None:
        host_network_services = {
            name for name, service in self.services.items() if service.get("network_mode") == "host"
        }
        self.assertEqual(host_network_services, {"netprobe"})

        netprobe = self.services["netprobe"]
        self.assertNotIn("volumes", netprobe)
        self.assertEqual(netprobe["environment"].get("NETPROBE_HOST"), "127.0.0.1")

    def test_all_published_ports_are_bound_to_loopback(self) -> None:
        for name, service in self.services.items():
            for port in service.get("ports", []):
                with self.subTest(service=name, port=port.get("published")):
                    self.assertEqual(port.get("host_ip"), "127.0.0.1")

    def test_sensitive_services_keep_container_hardening(self) -> None:
        for name in ("docker-socket-proxy", "netprobe"):
            service = self.services[name]
            with self.subTest(service=name):
                self.assertIs(service.get("read_only"), True)
                self.assertIn("ALL", service.get("cap_drop", []))
                self.assertIn("no-new-privileges:true", service.get("security_opt", []))
                self.assertNotIn("privileged", service)
                self.assertNotIn("cap_add", service)

    def test_socket_proxy_exposes_only_collector_read_categories(self) -> None:
        proxy = self.services["docker-socket-proxy"]
        environment = proxy["environment"]
        enabled = {key for key, value in environment.items() if value == "1"}

        self.assertEqual(enabled, {"CONTAINERS", "NETWORKS", "VERSION"})
        self.assertEqual(environment.get("POST"), "0")
        self.assertIn("@sha256:", proxy["image"])

    def test_sensitive_services_have_cpu_and_memory_limits(self) -> None:
        for name in ("docker-socket-proxy", "netprobe"):
            service = self.services[name]
            with self.subTest(service=name):
                self.assertGreater(float(service.get("cpus", 0)), 0)
                self.assertGreater(int(service.get("mem_limit", 0)), 0)

    def test_no_service_is_privileged_or_adds_capabilities(self) -> None:
        for name, service in self.services.items():
            with self.subTest(service=name):
                self.assertNotEqual(service.get("privileged"), True)
                self.assertFalse(service.get("cap_add"))


if __name__ == "__main__":
    unittest.main()

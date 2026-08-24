"""Docker client factory.

The Collector never touches /var/run/docker.sock directly — it only ever
talks to docker-socket-proxy over HTTP, exactly like any other client on the
network would. See docs/adr/0003-docker-access-isolation.md.
"""

import docker

from portwatch_backend.core.config import Settings


def make_docker_client(settings: Settings) -> docker.DockerClient:
    """Build a docker-py client pointed at the socket-proxy, not a raw socket."""

    return docker.DockerClient(
        base_url=settings.docker_proxy_url,
        version="auto",
        timeout=10,
    )

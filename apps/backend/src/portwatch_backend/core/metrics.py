"""Prometheus metrics — Fase 9 observability.

Exposed at `/metrics` (see app.py), scraped like any other Prometheus
target. Each `create_app()` call builds its own `PortWatchMetrics` with its
own `CollectorRegistry` instead of registering onto `prometheus_client`'s
process-global default registry — the test suite (and, at runtime, nothing
else) creates multiple `FastAPI` app instances in the same process, and
sharing one global registry across them would raise
"Duplicated timeseries in CollectorRegistry" on the second `create_app()`.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from fastapi import Request
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from starlette.responses import Response

Middleware = Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]


class PortWatchMetrics:
    """Owns one `CollectorRegistry` and every PortWatch series on it."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()

        self.http_requests_total = Counter(
            "portwatch_http_requests_total",
            "HTTP requests, by method, route template and status code.",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "portwatch_http_request_duration_seconds",
            "HTTP request duration in seconds, by method and route template.",
            ["method", "path"],
            registry=self.registry,
        )

        self.collector_cycles_total = Counter(
            "portwatch_collector_cycles_total",
            "Collector poll cycles, by outcome (success/failure).",
            ["outcome"],
            registry=self.registry,
        )
        self.collector_cycle_duration_seconds = Histogram(
            "portwatch_collector_cycle_duration_seconds",
            "Collector poll cycle duration in seconds, regardless of outcome.",
            registry=self.registry,
        )
        self.collector_last_success_timestamp_seconds = Gauge(
            "portwatch_collector_last_success_timestamp_seconds",
            "Unix timestamp of the last successful collection cycle.",
            registry=self.registry,
        )

        self.snapshot_generation = Gauge(
            "portwatch_snapshot_generation",
            "Generation number of the currently published Collector snapshot.",
            registry=self.registry,
        )
        self.containers_total = Gauge(
            "portwatch_containers_total",
            "Containers present in the currently published snapshot.",
            registry=self.registry,
        )
        self.ports_total = Gauge(
            "portwatch_ports_total",
            "Port entries present in the currently published snapshot.",
            registry=self.registry,
        )

    def observe_cycle_success(
        self,
        *,
        duration_seconds: float,
        generation: int,
        containers: int,
        ports: int,
        collected_at: datetime,
    ) -> None:
        self.collector_cycles_total.labels(outcome="success").inc()
        self.collector_cycle_duration_seconds.observe(duration_seconds)
        self.collector_last_success_timestamp_seconds.set(collected_at.timestamp())
        self.snapshot_generation.set(generation)
        self.containers_total.set(containers)
        self.ports_total.set(ports)

    def observe_cycle_failure(self, *, duration_seconds: float) -> None:
        self.collector_cycles_total.labels(outcome="failure").inc()
        self.collector_cycle_duration_seconds.observe(duration_seconds)


def _route_path_template(request: Request) -> str:
    """The matched route's path template (e.g. `/api/v1/containers/{id}`).

    Requests that never matched a route share one bounded label. Using their
    raw paths would let arbitrary 404 URLs create an unbounded number of
    Prometheus time series and grow process memory indefinitely.
    """

    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "__unmatched__"


def build_http_metrics_middleware(metrics: PortWatchMetrics) -> Middleware:
    """Return request-timing middleware bound to one `PortWatchMetrics`."""

    async def http_metrics_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
        except Exception:
            raise
        else:
            status_code = response.status_code
            return response
        finally:
            duration_seconds = time.monotonic() - start
            path = _route_path_template(request)
            metrics.http_requests_total.labels(
                method=request.method, path=path, status=str(status_code)
            ).inc()
            metrics.http_request_duration_seconds.labels(method=request.method, path=path).observe(
                duration_seconds
            )

    return http_metrics_middleware

"""`/metrics` (core/metrics.py, app.py) — Prometheus endpoint and the HTTP
request-timing middleware that feeds it. Each test builds its own app via
create_app() (see core/metrics.py's docstring on why: a shared
CollectorRegistry across FastAPI instances raises "Duplicated timeseries").
"""

import httpx
import pytest

from portwatch_backend.app import create_app
from portwatch_backend.core.config import Settings


@pytest.fixture
async def client():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _patch_settings(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token=token),
    )


async def test_metrics_requires_a_token_when_one_is_configured(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="s3cr3t")

    resp = await client.get("/metrics")

    assert resp.status_code == 401


async def test_metrics_is_open_when_no_token_is_configured(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="")

    resp = await client.get("/metrics")

    assert resp.status_code == 200


async def test_metrics_reports_prometheus_text_format(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_settings(monkeypatch, token="")

    resp = await client.get("/metrics")

    assert resp.headers["content-type"].startswith("text/plain")
    assert "portwatch_http_requests_total" in resp.text


async def test_metrics_counts_requests_by_route_template_not_raw_path(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # /health twice, then /metrics — a container id in the path (e.g.
    # /api/v1/containers/abc123) must never end up as its own label value,
    # or cardinality grows unbounded with every container ever queried.
    _patch_settings(monkeypatch, token="")
    await client.get("/health")
    await client.get("/health")

    resp = await client.get("/metrics")

    body = resp.text
    assert 'portwatch_http_requests_total{method="GET",path="/health",status="200"} 2.0' in body


async def test_metrics_scrape_request_itself_is_not_double_counted_before_its_own_response(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The /metrics handler snapshots the registry mid-request — its own
    # in-flight request can't have incremented the counter it's about to
    # report yet (the middleware records *after* call_next returns).
    _patch_settings(monkeypatch, token="")

    resp = await client.get("/metrics")

    assert 'path="/metrics"' not in resp.text

"""The app's lifespan must start/stop the Collector's background thread
cleanly — including when docker-socket-proxy is completely unreachable
(e.g. this test's own default settings, run outside any Docker network).
A failed poll cycle is caught and logged inside the Collector itself (see
collector/service.py), so app startup/shutdown must never hang or raise
just because Docker isn't reachable.
"""

from fastapi.testclient import TestClient

from portwatch_backend.app import app


def test_lifespan_starts_and_stops_the_collector_thread_cleanly() -> None:
    assert app.state.collector._thread is None  # not started outside a lifespan

    with TestClient(app) as client:
        assert app.state.collector._thread is not None
        assert app.state.collector._thread.is_alive()
        response = client.get("/health")
        assert response.status_code == 200

    # TestClient's context manager drives the real startup/shutdown events.
    assert app.state.collector._thread is None

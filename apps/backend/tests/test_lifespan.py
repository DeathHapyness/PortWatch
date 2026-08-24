"""The app lifespan starts/stops the Collector even without Docker."""

import httpx

from portwatch_backend.app import app


async def test_lifespan_starts_and_stops_the_collector_thread_cleanly() -> None:
    assert app.state.collector._thread is None  # not started outside a lifespan

    # Drive the ASGI lifespan directly. Starlette's synchronous TestClient
    # portal can deadlock on __enter__ with the current AnyIO/pytest-asyncio
    # combination, before the app's lifespan is even invoked. ASGITransport
    # deliberately leaves lifespan management to this explicit context.
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        assert app.state.collector._thread is not None
        assert app.state.collector._thread.is_alive()
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200

    # Exiting the lifespan context drives the real shutdown path.
    assert app.state.collector._thread is None

from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any

from portwatch_backend.app import create_app
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.events import SnapshotBroadcaster

NOW = datetime(2026, 8, 24, 18, 0, tzinfo=UTC)


async def test_store_publish_notifies_every_subscriber() -> None:
    broadcaster = SnapshotBroadcaster()
    store = SnapshotStore(on_publish=broadcaster.publish)

    async with broadcaster.subscribe() as first, broadcaster.subscribe() as second:
        snapshot = store.publish(collected_at=NOW)
        first_message, second_message = await asyncio.gather(first.get(), second.get())

    assert snapshot.generation == 1
    assert first_message == second_message
    assert first_message.type == "snapshot.updated"
    assert first_message.generation == 1
    assert first_message.collected_at == NOW


async def test_slow_subscriber_receives_only_the_latest_generation() -> None:
    broadcaster = SnapshotBroadcaster()

    async with broadcaster.subscribe() as events:
        broadcaster.publish(1, NOW)
        broadcaster.publish(2, NOW)
        broadcaster.publish(3, NOW)
        await asyncio.sleep(0)
        message = await asyncio.wait_for(events.get(), timeout=1)

    assert message.generation == 3
    assert events.empty()


def test_listener_failure_does_not_undo_a_published_snapshot() -> None:
    def fail(_generation: int, _collected_at: datetime) -> None:
        raise RuntimeError("listener failed")

    store = SnapshotStore(on_publish=fail)

    published = store.publish(collected_at=NOW)

    assert published.generation == 1
    assert store.read().generation == 1


async def test_websocket_receives_snapshot_updates_from_store_publish() -> None:
    now = datetime(2026, 8, 24, 18, 0, tzinfo=UTC)
    app = create_app()
    store = app.state.snapshot_store
    inbound: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    outbound: asyncio.Queue[MutableMapping[str, Any]] = asyncio.Queue()

    async def receive() -> MutableMapping[str, Any]:
        return await inbound.get()

    async def send(message: MutableMapping[str, Any]) -> None:
        await outbound.put(message)

    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "scheme": "ws",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "root_path": "",
        "path": "/api/v1/events",
        "raw_path": b"/api/v1/events",
        "query_string": b"",
        "headers": [],
        "subprotocols": [],
        "state": {},
    }
    await inbound.put({"type": "websocket.connect"})
    connection = asyncio.create_task(app(scope, receive, send))

    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"
    snapshot = store.publish(collected_at=now)
    sent = await asyncio.wait_for(outbound.get(), timeout=1)
    await inbound.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(connection, timeout=1)

    assert sent["type"] == "websocket.send"
    assert json.loads(sent["text"]) == {
        "type": "snapshot.updated",
        "generation": snapshot.generation,
        "collected_at": now.isoformat().replace("+00:00", "Z"),
    }

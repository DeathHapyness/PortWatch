from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from portwatch_backend.api.events import MAX_AUTH_MESSAGE_BYTES, MAX_AUTH_TOKEN_BYTES
from portwatch_backend.app import create_app
from portwatch_backend.collector.state import SnapshotStore
from portwatch_backend.core.config import Settings
from portwatch_backend.core.events import (
    BroadcasterClosedError,
    SnapshotBroadcaster,
    SubscriberLimitError,
)

NOW = datetime(2026, 8, 24, 18, 0, tzinfo=UTC)


def _websocket_scope(headers: Sequence[tuple[bytes, bytes]] = ()) -> dict[str, Any]:
    return {
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
        "headers": list(headers),
        "subprotocols": [],
        "state": {},
    }


_Connection = tuple[
    asyncio.Queue[dict[str, Any]], asyncio.Queue[MutableMapping[str, Any]], asyncio.Task[None]
]


async def _open_connection(
    app: FastAPI, *, headers: Sequence[tuple[bytes, bytes]] = ()
) -> _Connection:
    """Drive the ASGI websocket handshake by hand, same rationale as
    test_lifespan.py's ASGITransport approach: httpx has no websocket
    support, and the synchronous TestClient portal can deadlock with the
    current FastAPI/Starlette combination (see that file's comment) — this
    talks the real ASGI protocol directly instead, with the app as any
    other callable."""

    inbound: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    outbound: asyncio.Queue[MutableMapping[str, Any]] = asyncio.Queue()

    async def receive() -> MutableMapping[str, Any]:
        return await inbound.get()

    async def send(message: MutableMapping[str, Any]) -> None:
        await outbound.put(message)

    await inbound.put({"type": "websocket.connect"})
    connection = asyncio.create_task(app(_websocket_scope(headers), receive, send))
    return inbound, outbound, connection


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

    inbound, outbound, connection = await _open_connection(app)

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


async def test_websocket_rejects_an_invalid_bearer_header_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression test: an HTTPException raised before websocket.accept()
    # used to propagate to the app's global HTTPException handler, which
    # builds an HTTP JSONResponse and reads request.state.request_id — a
    # crash (AttributeError), since request_id_middleware is HTTP-only and
    # never runs for a websocket scope. The endpoint must catch this itself
    # and close cleanly instead (see api/events.py).
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token="s3cr3t"),
    )
    app = create_app()

    _inbound, outbound, connection = await _open_connection(
        app, headers=[(b"authorization", b"Bearer wrong")]
    )

    closed = await asyncio.wait_for(outbound.get(), timeout=1)
    await asyncio.wait_for(connection, timeout=1)

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}
    assert connection.exception() is None


async def test_websocket_accepts_a_valid_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token="s3cr3t"),
    )
    app = create_app()

    inbound, outbound, connection = await _open_connection(
        app, headers=[(b"authorization", b"Bearer s3cr3t")]
    )

    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"

    await inbound.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(connection, timeout=1)


async def test_websocket_accepts_token_in_first_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token="s3cr3t"),
    )
    app = create_app()

    inbound, outbound, connection = await _open_connection(app)

    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"
    await inbound.put({"type": "websocket.receive", "text": '{"token":"s3cr3t"}'})
    await inbound.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(connection, timeout=1)


async def test_websocket_rejects_wrong_token_in_first_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token="s3cr3t"),
    )
    app = create_app()

    inbound, outbound, connection = await _open_connection(app)

    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"
    await inbound.put({"type": "websocket.receive", "text": '{"token":"wrong"}'})
    closed = await asyncio.wait_for(outbound.get(), timeout=1)
    await asyncio.wait_for(connection, timeout=1)

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


async def test_websocket_rejects_missing_first_message_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token="s3cr3t"),
    )
    monkeypatch.setattr(
        "portwatch_backend.api.events.AUTH_MESSAGE_TIMEOUT_SECONDS",
        0.01,
    )
    app = create_app()

    _inbound, outbound, connection = await _open_connection(app)

    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"
    closed = await asyncio.wait_for(outbound.get(), timeout=1)
    await asyncio.wait_for(connection, timeout=1)

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


# --- SnapshotBroadcaster.close() — graceful shutdown --------------------


async def test_close_wakes_every_subscriber_with_none() -> None:
    broadcaster = SnapshotBroadcaster()

    async with broadcaster.subscribe() as first, broadcaster.subscribe() as second:
        broadcaster.close()
        first_message, second_message = await asyncio.gather(
            asyncio.wait_for(first.get(), timeout=1),
            asyncio.wait_for(second.get(), timeout=1),
        )

    assert first_message is None
    assert second_message is None


def test_close_is_idempotent() -> None:
    broadcaster = SnapshotBroadcaster()

    broadcaster.close()
    broadcaster.close()  # must not raise

    assert broadcaster.closed is True


async def test_subscribe_after_close_is_rejected() -> None:
    broadcaster = SnapshotBroadcaster()
    broadcaster.close()

    with pytest.raises(BroadcasterClosedError):
        async with broadcaster.subscribe():
            pass


def test_publish_after_close_is_a_noop() -> None:
    broadcaster = SnapshotBroadcaster()
    broadcaster.close()

    broadcaster.publish(1, NOW)  # must not raise or un-close

    assert broadcaster.closed is True


async def test_websocket_closes_gracefully_when_the_broadcaster_shuts_down() -> None:
    app = create_app()
    _inbound, outbound, connection = await _open_connection(app)

    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"

    app.state.event_broadcaster.close()
    closed = await asyncio.wait_for(outbound.get(), timeout=1)
    await asyncio.wait_for(connection, timeout=1)

    assert closed == {"type": "websocket.close", "code": 1001, "reason": ""}
    assert connection.exception() is None


async def test_websocket_rejects_new_connections_once_the_broadcaster_is_closed() -> None:
    app = create_app()
    app.state.event_broadcaster.close()

    _inbound, outbound, connection = await _open_connection(app)

    closed = await asyncio.wait_for(outbound.get(), timeout=1)
    await asyncio.wait_for(connection, timeout=1)

    # Rejected before accept() — the very first outbound message is already
    # the close frame, not an accept followed by a close.
    assert closed == {"type": "websocket.close", "code": 1001, "reason": ""}
    assert connection.exception() is None


# --- first-message auth hardening ----------------------------------------


async def _connect_and_send_first_message(
    monkeypatch: pytest.MonkeyPatch, raw_message: str
) -> MutableMapping[str, Any]:
    monkeypatch.setattr(
        "portwatch_backend.core.auth.get_settings",
        lambda: Settings(api_token="s3cr3t"),
    )
    app = create_app()

    inbound, outbound, connection = await _open_connection(app)
    accepted = await asyncio.wait_for(outbound.get(), timeout=1)
    assert accepted["type"] == "websocket.accept"

    await inbound.put({"type": "websocket.receive", "text": raw_message})
    closed = await asyncio.wait_for(outbound.get(), timeout=1)
    await asyncio.wait_for(connection, timeout=1)
    return closed


async def test_websocket_rejects_an_oversized_auth_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The message-size check runs on the raw string before JSON is even
    # parsed, so a single huge token value trips it first — this isolates
    # that check from the (separately tested) token-size one below.
    oversized = json.dumps({"token": "x" * (MAX_AUTH_MESSAGE_BYTES + 1)})
    closed = await _connect_and_send_first_message(monkeypatch, oversized)

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


async def test_websocket_rejects_an_oversized_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # Comfortably under MAX_AUTH_MESSAGE_BYTES, so this exercises the
    # token-specific size check, not the whole-message one above.
    oversized_token = json.dumps({"token": "x" * (MAX_AUTH_TOKEN_BYTES + 1)})
    closed = await _connect_and_send_first_message(monkeypatch, oversized_token)

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


async def test_websocket_rejects_a_duplicate_token_field(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = await _connect_and_send_first_message(
        monkeypatch, '{"token":"s3cr3t","token":"s3cr3t"}'
    )

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


async def test_websocket_rejects_an_auth_message_with_extra_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = await _connect_and_send_first_message(
        monkeypatch, json.dumps({"token": "s3cr3t", "extra": "field"})
    )

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


async def test_websocket_rejects_a_whitespace_only_token(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = await _connect_and_send_first_message(monkeypatch, json.dumps({"token": "   "}))

    assert closed == {"type": "websocket.close", "code": 1008, "reason": ""}


# --- subscriber limit (resource-exhaustion hardening) ----------------------


def test_broadcaster_rejects_a_non_positive_max_subscribers() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        SnapshotBroadcaster(max_subscribers=0)


async def test_subscribe_raises_once_the_limit_is_reached() -> None:
    broadcaster = SnapshotBroadcaster(max_subscribers=1)

    async with broadcaster.subscribe():
        with pytest.raises(SubscriberLimitError):
            async with broadcaster.subscribe():
                pass


async def test_a_freed_slot_can_be_reused_after_the_limit_was_hit() -> None:
    broadcaster = SnapshotBroadcaster(max_subscribers=1)

    async with broadcaster.subscribe():
        with pytest.raises(SubscriberLimitError):
            async with broadcaster.subscribe():
                pass

    # The first subscription's context manager has exited (slot freed) — a
    # new one must succeed rather than staying rejected forever.
    async with broadcaster.subscribe():
        pass


async def test_rejecting_over_the_limit_does_not_leak_a_phantom_subscriber() -> None:
    # A rejected subscribe() must not have added itself to the set it just
    # checked — otherwise the limit would ratchet down permanently.
    broadcaster = SnapshotBroadcaster(max_subscribers=1)

    async with broadcaster.subscribe():
        for _ in range(5):
            with pytest.raises(SubscriberLimitError):
                async with broadcaster.subscribe():
                    pass

    async with broadcaster.subscribe():
        pass


async def test_websocket_closes_with_1013_once_the_subscriber_limit_is_reached() -> None:
    app = create_app()
    app.state.event_broadcaster = SnapshotBroadcaster(max_subscribers=1)

    # First connection takes the only slot and stays open.
    first_inbound, first_outbound, first_connection = await _open_connection(app)
    first_accepted = await asyncio.wait_for(first_outbound.get(), timeout=1)
    assert first_accepted["type"] == "websocket.accept"

    # Second connection is accepted (auth happens before subscribing) but
    # then rejected for being over the concurrent-subscriber limit.
    _second_inbound, second_outbound, second_connection = await _open_connection(app)
    second_accepted = await asyncio.wait_for(second_outbound.get(), timeout=1)
    assert second_accepted["type"] == "websocket.accept"
    second_closed = await asyncio.wait_for(second_outbound.get(), timeout=1)
    await asyncio.wait_for(second_connection, timeout=1)

    assert second_closed == {"type": "websocket.close", "code": 1013, "reason": ""}
    assert second_connection.exception() is None

    await first_inbound.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(first_connection, timeout=1)

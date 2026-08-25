"""WebSocket stream for live snapshot invalidation notifications."""

import asyncio
import json
from typing import Any

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status

from portwatch_backend.core.auth import validate_api_token
from portwatch_backend.core.events import SnapshotBroadcaster

AUTH_MESSAGE_TIMEOUT_SECONDS = 5.0


def _token_from_message(raw_message: str) -> str:
    payload: Any = json.loads(raw_message)
    if not isinstance(payload, dict):
        raise ValueError("authentication message must be an object")

    token = payload.get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("authentication message must contain a token")
    return token


async def _authenticate(websocket: WebSocket) -> bool:
    authorization = websocket.headers.get("authorization")
    if authorization is not None:
        try:
            validate_api_token(authorization)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False
        await websocket.accept()
        return True

    try:
        validate_api_token(None)
    except HTTPException:
        # Authentication is configured, but browsers cannot set a custom
        # Authorization header during the WebSocket handshake. Accept first,
        # then require the token as the connection's first application message.
        await websocket.accept()
        try:
            message = await asyncio.wait_for(
                websocket.receive(),
                timeout=AUTH_MESSAGE_TIMEOUT_SECONDS,
            )
            if message["type"] == "websocket.disconnect":
                return False
            raw_message = message.get("text")
            if not isinstance(raw_message, str):
                raise ValueError("authentication message must be text")
            token = _token_from_message(raw_message)
            validate_api_token(f"Bearer {token}")
        except (TimeoutError, HTTPException, ValueError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False
        return True

    # Empty api_token on loopback keeps the existing unauthenticated behavior.
    await websocket.accept()
    return True


async def snapshot_events(websocket: WebSocket) -> None:
    if not await _authenticate(websocket):
        return
    broadcaster: SnapshotBroadcaster = websocket.app.state.event_broadcaster

    async with broadcaster.subscribe() as events:
        event_task = asyncio.create_task(events.get())
        receive_task = asyncio.create_task(websocket.receive())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {event_task, receive_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if receive_task in done:
                    message = receive_task.result()
                    if message["type"] == "websocket.disconnect":
                        return
                    receive_task = asyncio.create_task(websocket.receive())

                if event_task in done:
                    event = event_task.result()
                    await websocket.send_json(event.model_dump(mode="json"))
                    event_task = asyncio.create_task(events.get())
        except WebSocketDisconnect:
            return
        finally:
            event_task.cancel()
            receive_task.cancel()
            await asyncio.gather(event_task, receive_task, return_exceptions=True)

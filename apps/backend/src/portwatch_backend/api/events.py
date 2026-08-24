"""WebSocket stream for live snapshot invalidation notifications."""

import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from portwatch_backend.core.auth import validate_api_token
from portwatch_backend.core.events import SnapshotBroadcaster


async def snapshot_events(websocket: WebSocket) -> None:
    validate_api_token(websocket.headers.get("authorization"))
    broadcaster: SnapshotBroadcaster = websocket.app.state.event_broadcaster

    await websocket.accept()
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

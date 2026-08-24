"""WebSocket stream for live snapshot invalidation notifications."""

import asyncio

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status

from portwatch_backend.core.auth import validate_api_token
from portwatch_backend.core.events import SnapshotBroadcaster


async def snapshot_events(websocket: WebSocket) -> None:
    try:
        validate_api_token(websocket.headers.get("authorization"))
    except HTTPException:
        # The app's global HTTPException handler (app.py's
        # problem_detail_handler) builds an HTTP JSONResponse and reads
        # request.state.request_id — neither makes sense for a websocket
        # scope, and request_id_middleware is HTTP-only (app.middleware
        # "http") so that attribute was never even set here. Letting the
        # HTTPException propagate crashes the connection with an unhandled
        # AttributeError instead of a clean auth rejection. Close directly.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
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

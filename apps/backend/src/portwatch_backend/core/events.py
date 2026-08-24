"""Thread-safe fan-out for snapshot invalidation events.

The Collector publishes from a dedicated thread, while WebSocket subscribers
consume on one or more asyncio event loops. Each subscriber gets a single-slot
queue: when a slow client falls behind, only the newest generation matters
because the dashboard refetches the complete snapshot through the HTTP API.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from portwatch_backend.core.schemas import EventMessage


@dataclass(frozen=True, slots=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[EventMessage]


def _offer_latest(queue: asyncio.Queue[EventMessage], message: EventMessage) -> None:
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(message)


class SnapshotBroadcaster:
    """Fan one snapshot-generation notification out to every subscriber."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: set[_Subscriber] = set()
        self._last_generation = 0

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[EventMessage]]:
        subscriber = _Subscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=1),
        )
        with self._lock:
            self._subscribers.add(subscriber)
        try:
            yield subscriber.queue
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

    def publish(self, generation: int, collected_at: datetime) -> None:
        """Notify subscribers from any thread; duplicate/old events are ignored."""

        message = EventMessage(generation=generation, collected_at=collected_at)
        with self._lock:
            if generation <= self._last_generation:
                return
            self._last_generation = generation
            subscribers = tuple(self._subscribers)

        closed: list[_Subscriber] = []
        for subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(_offer_latest, subscriber.queue, message)
            except RuntimeError:
                # The subscriber's loop closed between snapshotting the set
                # and scheduling delivery. Remove it without affecting the
                # Collector's successful snapshot publication.
                closed.append(subscriber)

        if closed:
            with self._lock:
                self._subscribers.difference_update(closed)

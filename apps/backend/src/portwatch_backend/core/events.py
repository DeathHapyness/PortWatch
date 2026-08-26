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

type BroadcastItem = EventMessage | None


class BroadcasterClosedError(RuntimeError):
    """Raised when a subscription starts after shutdown has begun."""


class SubscriberLimitError(RuntimeError):
    """Raised when the configured concurrent subscriber limit is reached."""


@dataclass(frozen=True, slots=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[BroadcastItem]


def _offer_latest(queue: asyncio.Queue[BroadcastItem], message: BroadcastItem) -> None:
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(message)


class SnapshotBroadcaster:
    """Fan one snapshot-generation notification out to every subscriber."""

    def __init__(self, *, max_subscribers: int = 128) -> None:
        if max_subscribers < 1:
            raise ValueError("max_subscribers must be at least 1")
        self._lock = Lock()
        self._subscribers: set[_Subscriber] = set()
        self._max_subscribers = max_subscribers
        self._last_generation = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[BroadcastItem]]:
        subscriber = _Subscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=1),
        )
        with self._lock:
            if self._closed:
                raise BroadcasterClosedError("snapshot broadcaster is closed")
            if len(self._subscribers) >= self._max_subscribers:
                raise SubscriberLimitError("snapshot subscriber limit reached")
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
            if self._closed or generation <= self._last_generation:
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

    def close(self) -> None:
        """Stop future publications and wake every subscriber exactly once."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            subscribers = tuple(self._subscribers)

        stale: list[_Subscriber] = []
        for subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(_offer_latest, subscriber.queue, None)
            except RuntimeError:
                stale.append(subscriber)

        if stale:
            with self._lock:
                self._subscribers.difference_update(stale)

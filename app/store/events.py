# app/store/events.py

from __future__ import annotations

import redis.asyncio as redis
from pydantic import ValidationError

from app.model import TaskEvent, TaskEventType
from app.store.redis import KEY_EVENTS, KEY_EVENTS_CLUSTER

# clusterEventTypes are the rare lifecycle events mirrored into a second retained
# list so a burst of started/completed events can't evict them from the main
# 200-entry stream.
CLUSTER_EVENT_TYPES: set[TaskEventType | str] = {
    TaskEventType.NODE_JOINED,
    TaskEventType.NODE_DEAD,
    TaskEventType.RECLAIMED,
}


class EventStore:
    MAX_EVENTS = 200  # max no. of events stored in `KEY_EVENTS`

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    async def push(self, task_event: TaskEvent) -> None:
        """Append an event, trim to 200, and mirror cluster lifecycle events."""

        data = task_event.model_dump_json()

        pipe = self.client.pipeline(transaction=False)

        pipe.lpush(KEY_EVENTS, data)
        pipe.ltrim(KEY_EVENTS, 0, self.MAX_EVENTS)

        # Mirror rare cluster lifecycle events to prevent eviction by high-volume events
        if task_event.type in CLUSTER_EVENT_TYPES:
            pipe.lpush(KEY_EVENTS_CLUSTER, data)
            pipe.ltrim(KEY_EVENTS_CLUSTER, 0, 199)

        await pipe.execute()

    async def list(self, limit: int) -> list[TaskEvent]:
        """Fetch the most recent events (newest first)."""
        return await self._list(KEY_EVENTS, limit)

    async def list_cluster(self, limit: int) -> list[TaskEvent]:
        """Fetch the most recent cluster lifecycle events (newest first)."""
        return await self._list(KEY_EVENTS_CLUSTER, limit)

    async def _list(self, key: str, limit: int) -> list[TaskEvent]:
        """Internal helper to retrieve and parse events from Redis."""
        # Sanitize non-positive limits to default fallback
        if limit <= 0:
            limit = 50

        # Cap reads so callers cannot accidentally request an unbounded feed.
        limit = min(limit, self.MAX_EVENTS)

        values = await self.client.lrange(key, 0, limit - 1)

        events: list[TaskEvent] = []

        for value in values:
            try:
                # Parse directly from raw JSON string/bytes directly into TaskEvent.
                # Avoids intermediate Python dict creation with `json.loads()`.
                events.append(TaskEvent.model_validate_json(value))
            except (ValidationError, ValueError, TypeError):
                # ignore corrupt of marlformed data
                continue

        return events

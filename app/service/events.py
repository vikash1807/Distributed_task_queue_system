# app/service/events.py

from __future__ import annotations

from app.model import TaskEvent
from app.store.events import EventStore


class EventService:
    """Application service for querying task lifecycle events."""

    def __init__(self, event_store: EventStore) -> None:
        self.event_store = event_store

    async def list_events(self, limit: int = 50) -> list[TaskEvent]:
        return await self.event_store.list(limit)

    async def list_cluster_events(self, limit: int = 50) -> list[TaskEvent]:
        return await self.event_store.list_cluster(limit)
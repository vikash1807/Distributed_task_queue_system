# app/queue/queue.py

from __future__ import annotations

from pathlib import Path
from typing import Optional

import redis.asyncio as redis

from app.core import settings
from app.model import Task, TaskNotFound
from app.store import TaskStore, KEY_READY, KEY_READY_SIGNAL


SCRIPTS_DIR = Path(__file__).parent / "scripts"


def load_script(name: str) -> str:
    """Read a Lua script from the broker's scripts directory."""
    return (SCRIPTS_DIR / name).read_text(encoding="utf-8")


class PriorityQueue:

    def __init__(self, client: redis.Redis, task_store: TaskStore):
        self.task_store = task_store
        self.client = client
        self._enqueue = client.register_script(load_script("enqueue.lua"))

    async def enqueue(self, task: Task) -> None:
        """Add a task ID to ready (score = -priority), then ring the doorbell."""

        await self._enqueue(
            keys=[
                KEY_READY,
                KEY_READY_SIGNAL
            ],
            args=[
                task.id,
                task.priority,
                settings.signal_cap
            ]
        )
    
    async def dequeue(self) -> Optional[Task]:
        """Pop the Highest priority task (lowest score)."""

        results = await self.client.zpopmin(KEY_READY, 1)

        if not results:
            return None
        
        task_id, _score = results[0]

        try:
            task = await self.task_store.get(task_id)
            return task
        except TaskNotFound:
            return None # record vanished (e.g. flushed) after we popped its ID
        
    async def size(self) -> int:
        return await self.client.zcard(KEY_READY)
    
    
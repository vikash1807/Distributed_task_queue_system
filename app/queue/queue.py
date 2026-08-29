# app/queue/queue.py

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis

from app.model import Task, TaskNotFound
from app.store import TaskStore, KEY_READY



class PriorityQueue:

    def __init__(self, client: redis.Redis, task_store: TaskStore):
        self.task_store = task_store
        self.client = client

    async def enqueue(self, task: Task) -> None:
        """Add a task ID to ready (score = -priority)."""

        await self.client.zadd(
            KEY_READY,
            {task.id : float(-task.priority)}
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
    
    
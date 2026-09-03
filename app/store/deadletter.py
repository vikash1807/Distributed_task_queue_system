# app/store/deadletter.py

from __future__ import annotations

import json
from pathlib import Path

import redis.asyncio as redis

from app.model import FailedTask, Task
from app.store.redis import KEY_DEADLETTER, key_task


_DEADLETTER_LUA = (
    Path(__file__).parent / "scripts" / "deadletter.lua"
).read_text(encoding="utf-8")


class DeadLetterStore:
    def __init__(self, client: redis.Redis) -> None:
        self.client = client
        self._push = client.register_script(_DEADLETTER_LUA)
    
    async def push(self, task: Task, failed_task: FailedTask):
        """
        Atomically update the task.status to failed and push a failed task onto the DLQ, newest task first."""
        
        await self._push(
            keys=[
                key_task(task.id),
                KEY_DEADLETTER
            ],
            args=[
                task.status.value,
                json.dumps(failed_task.to_dict(),)
            ]
        )

    async def list(self, offset: int, limit: int) -> list[FailedTask]:
        """Return a paginated slice of failed tasks."""

        if offset < 0:
            raise ValueError("offset must be >= 0")

        if limit <= 0:
            raise ValueError("limit must be > 0")

        items = await self.client.lrange(
            KEY_DEADLETTER,
            offset,
            offset + limit - 1,
        )

        failed_tasks: list[FailedTask] = []

        for item in items:
            try:
                data = json.loads(item)
                failed_tasks.append(
                    FailedTask.from_json_dict(data)
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                # Ignore malformed DLQ entries.
                continue

        return failed_tasks
    
    # Used by the redrive endpoint to move failed tasks back into the ready queue.
    async def drain_all(self) -> list[FailedTask]:
        """Pop every entry off the list and return failed tasks(for redrive.)"""

        failed_tasks: list[FailedTask] = []

        while True:
            item = await self.client.rpop(KEY_DEADLETTER)

            if item is None:
                break

            try:
                data = json.loads(item)
                failed_tasks.append(
                    FailedTask.from_json_dict(data)
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        return failed_tasks
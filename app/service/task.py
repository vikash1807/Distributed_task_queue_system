from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from app.model import Task, TaskStatus, FailedTask
from app.queue import PriorityQueue
from app.store import TaskStore, DeadLetterStore


class DuplicateTaskError(Exception):
    """Raised when a caller submits a task ID that already exists."""


def generate_task_id() -> str:
    return f"task-{secrets.token_hex(12)}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskService:
    def __init__(
        self,
        task_store: TaskStore,
        task_queue: PriorityQueue,
        dead_letter: DeadLetterStore,
    ) -> None:
        self.task_store = task_store
        self.task_queue = task_queue
        self.dead_letter = dead_letter

    async def submit_task(
        self,
        *,
        id: str = "",
        type: str = "",
        payload: Any = None,
        priority: int = 0,
        delay: int = 0,
        max_retries: int = 0,
    ) -> Task:
        task_id = id or generate_task_id()

        if id and await self.task_store.exists(task_id):
            raise DuplicateTaskError(task_id)

        task = Task(
            id=task_id,
            type=type,
            payload=payload,
            priority=priority,
            delay=delay,
            max_retries=max_retries,
            status=TaskStatus.PENDING,
            created_at=utc_now(),
        )

        await self.task_store.save(task)
        await self.task_queue.enqueue(task)

        return task

    async def get_task(self, task_id: str) -> Task:
        return await self.task_store.get(task_id)

    async def get_failed_tasks(self, offset: int, limit: int) -> list[FailedTask]:
        return await self.dead_letter.list(offset, limit)
    
    async def redrive_failed_tasks(self) -> dict[str, Any]:

        failed_tasks: list[FailedTask] = self.dead_letter.drain_all()

        if not failed_tasks:
            return {
                "redriven": 0,
                "totao": 0
            }

        for failed_task in failed_tasks:
            task = failed_task.task

            task.retries = 0
            task.status = TaskStatus.PENDING
            task.error = ""

            try:
                await self.task_store.save(task)
                await self.task_queue.enqueue(task)
            except Exception:
                continue

            redriven += 1
        
        return {
        "redriven": redriven,
        "total": len(failed_tasks),
    }

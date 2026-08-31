# app/store/task.py

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

import redis.asyncio as redis

from app.model import Task, TaskStatus, TaskNotFound, parse_status
from app.store.redis import key_task


def task_to_hash(task: Task) -> dict[str, Any]:
    "Convert a task into redis hash field."
    return {
        "id": task.id,
        "type": task.type,
        "payload": json.dumps(task.payload) if task.payload is not None else "",
        "priority": task.priority,
        "delay": task.delay,
        "max_retries": task.max_retries,
        "retries": task.retries,
        "status": task.status.value,
        "created_at": (
            task.created_at.isoformat()
            if task.created_at is not None
            else ""
        ),
        "error": task.error,
        "owner": task.owner,
    }

def hash_to_task(data: Dict[str, Any]) -> Task:
    """Convert a Redis hash back into a Task."""
    payload: Any = None

    if data.get("payload"):
        try:
            payload = json.loads(data["payload"])
        except (json.JSONDecodeError, TypeError):
            payload = data["payload"]

    created_at: datetime | None = None

    if data.get("created_at"):
        try:
            created_at = datetime.fromisoformat(data["created_at"])
        except ValueError:
            created_at = None

    try:
        status = TaskStatus(data.get("status", "pending"))
    except ValueError:
        status = TaskStatus.PENDING
    
    return Task(
        id=data.get("id", ""),
        type=data.get("type", ""),
        payload=payload,
        priority=int(data.get("priority") or 0),
        delay=int(data.get("delay") or 0),
        max_retries=int(data.get("max_retries") or 0),
        retries=int(data.get("retries") or 0),
        status=parse_status(data.get("status", "pending")),
        created_at=created_at,
        error=data.get("error", ""),
        owner=data.get("owner", ""),
    )



class TaskStore:

    def __init__(self, client: redis.Redis) -> None:
        self.client = client
    
    async def save(self, task: Task) -> None:
        """Create or fully overwrite a task's canonical record."""
        await self.client.hset(
            key_task(task.id),
            mapping = task_to_hash(task)
        )
    
    async def get(self, task_id: str):
        """Returns a task by id."""
        data = await self.client.hgetall(key_task(task_id))

        if not data:
            raise TaskNotFound(task_id)
        
        task = hash_to_task(data)
        return task

    async def exists(self, task_id: str) -> bool:
        """Return True if a record with this id already exists."""

        return bool(await self.client.exists(key_task(task_id)))

    async def get_many(self, task_ids: List[str]) -> List[Task]:
        if not task_ids:
            return []
        
        async with self.client.pipeline(transaction=False) as pipe:
            for task_id in task_ids:
                pipe.hgetall(key_task(task_id))
            
            results = await pipe.execute()
        
        return [hash_to_task(data) for data in results if data]

    
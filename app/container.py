from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis

from app.core.config import Config
from app.queue import PriorityQueue
from app.service.task import TaskService
from app.store import TaskStore


@dataclass
class AppContainer:
    redis: redis.Redis
    task_store: TaskStore
    task_queue: PriorityQueue
    task_service: TaskService


def build_container(client: redis.Redis, config: Config) -> AppContainer:
    task_store = TaskStore(client)
    task_queue = PriorityQueue(client, task_store)
    task_service = TaskService(
        task_store=task_store,
        task_queue=task_queue,
    )

    return AppContainer(
        redis=client,
        task_store=task_store,
        task_queue=task_queue,
        task_service=task_service,
    )

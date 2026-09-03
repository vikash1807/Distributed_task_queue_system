from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis

from app.core.config import Config
from app.queue import PriorityQueue, DelayedScheduler
from app.service.task import TaskService
from app.store import TaskStore, DeadLetterStore


@dataclass
class AppContainer:
    redis: redis.Redis
    task_store: TaskStore
    task_queue: PriorityQueue
    delayed_scheduler: DelayedScheduler
    dead_letter: DeadLetterStore
    task_service: TaskService


def build_container(client: redis.Redis, config: Config) -> AppContainer:
    task_store = TaskStore(client)
    task_queue = PriorityQueue(client, task_store)
    
    delayed_scheduler = DelayedScheduler(client, task_queue, task_store)
    dead_letter = DeadLetterStore(client)


    task_service = TaskService(
        task_store=task_store,
        task_queue=task_queue,
        dead_letter=dead_letter,
    )

    return AppContainer(
        redis=client,
        task_store=task_store,
        task_queue=task_queue,
        delayed_scheduler=delayed_scheduler,
        dead_letter=dead_letter,
        task_service=task_service,
    )

# app/container.py

from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis

from app.core.config import Config
from app.queue import PriorityQueue, DelayedScheduler
from app.service import TaskService, MetricService
from app.store import TaskStore, DeadLetterStore, MetricStore


@dataclass
class AppContainer:
    redis: redis.Redis
    task_store: TaskStore
    task_queue: PriorityQueue
    delayed_scheduler: DelayedScheduler
    dead_letter: DeadLetterStore
    metric_store: MetricStore
    task_service: TaskService
    metric_service: MetricService


def build_container(client: redis.Redis, config: Config) -> AppContainer:
    task_store = TaskStore(client)
    task_queue = PriorityQueue(client, task_store)
    
    delayed_scheduler = DelayedScheduler(client, task_queue, task_store)
    dead_letter = DeadLetterStore(client)
    metric_store = MetricStore(client)


    task_service = TaskService(
        task_store=task_store,
        task_queue=task_queue,
        delayed_queue=delayed_scheduler,
        dead_letter=dead_letter,
        metric_store=metric_store,
    )

    metric_service = MetricService(
        client=client,
        task_queue=task_queue,
        metric_store=metric_store
    )

    return AppContainer(
        redis=client,
        task_queue=task_queue,
        delayed_scheduler=delayed_scheduler,
        dead_letter=dead_letter,
        task_store=task_store,
        metric_store=metric_store,
        task_service=task_service,
        metric_service=metric_service,
    )

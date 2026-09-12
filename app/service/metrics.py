# app/service/metric.py

from __future__ import annotations

import redis.asyncio as redis

from app.queue import PriorityQueue
from app.model import Metrics, EnhancedMetrics
from app.store import (
    MetricStore,
    KEY_READY,
    KEY_DEADLETTER,
    KEY_DELAYED,
    KEY_METRICS,
    KEY_PROCESSING,
)


class MetricService:
    def __init__(
        self,
        client: redis.Redis,
        task_queue: PriorityQueue,
        metric_store: MetricStore,
    ) -> None:
        self.client = client
        self.metric_store = metric_store
        self.task_queue = task_queue
    
    async def get_metrics(self) -> Metrics:
        """Return the current queue metrics"""
        queue_size = await self.task_queue.size()
        active_workers = await self.client.zcard(KEY_PROCESSING) # current leased/in-flight tasks

        return await self.metric_store.get_metrics(queue_size, active_workers)
    
    async def get_enhanced_metrics(self) -> EnhancedMetrics:
        """Return metrics with delayed, DLQ, and submission information."""
        queue_size = await self.client.zcard(KEY_READY)
        active_workers = await self.client.zcard(KEY_PROCESSING)
        delayed_size = await self.client.zcard(KEY_DELAYED)
        dead_letter_size = await self.client.llen(KEY_DEADLETTER)

        return await self.metric_store.get_enhanced_metrics(
            queue_size=queue_size,
            active_workers=active_workers,
            delayed_size=delayed_size,
            dead_letter_size=dead_letter_size,
        )
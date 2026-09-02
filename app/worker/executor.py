# app/worker/executor.py

"""Execute a single claimed task and acknowledge its outcome."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.broker import LeaseNotHeld, RedisBroker
from app.handler import Registry, create_registry
from app.model import Task


logger = logging.getLogger(__name__)
DEFAULT_DRAIN_TIMEOUT = 5.0  # seconds


@dataclass
class ExecutorDeps:
    broker: RedisBroker
    handlers: Registry
    drain_timeout: float = DEFAULT_DRAIN_TIMEOUT


class Executor:
    def __init__(self, deps: ExecutorDeps) -> None:
        self.broker = deps.broker
        self.handlers = deps.handlers
        self.dran_timeout = deps.drain_timeout

    
    async def execute(self, task: Task) -> None:
        """Run a task and ACK on success and NACK on failure."""

        try:
            handler = self.handlers.get(task.type)

            result = await asyncio.wait_for(
                handler(task),
                timeout=self.dran_timeout
            )

            await self.broker.ack(task.id)

            logger.info("task completed task_id=%s detai=%s", task.id, result.detail)
        
        except LeaseNotHeld:
            logger.exception("lease no longer hold task_id=%s", task.id)
        
        except Exception:
            logger.exception("task failed task_id=%s", task.id)
        
            try:
                await self.broker.nack(task.id)
            except LeaseNotHeld:
                logger.exception("lease no longer held while nacking task_id=%s", task.id)


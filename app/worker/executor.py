# app/worker/executor.py

"""Execute a single claimed task and route it's outcome to ack, retry or DLQ. """

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.broker import LeaseNotHeld, RedisBroker
from app.handler import Registry
from app.model import Task, TaskStatus, FailedTask
from app.queue import DelayedScheduler
from app.store import TaskStore, DeadLetterStore



logger = logging.getLogger(__name__)
DEFAULT_DRAIN_TIMEOUT = 5.0  # seconds

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def backoff_delay(retries: int) -> float:
    """Return retry delay for a given (post-increment) retry count: exponential 2^retries seconds, capped at 60s."""
    return float(min(2 ** retries, 60))


@dataclass
class ExecutorDeps:
    broker: RedisBroker
    handlers: Registry
    task_store: TaskStore
    delayed: DelayedScheduler
    dead_letter: DeadLetterStore
    drain_timeout: float = DEFAULT_DRAIN_TIMEOUT


class Executor:
    def __init__(self, deps: ExecutorDeps) -> None:
        self.broker = deps.broker
        self.handlers = deps.handlers
        self.task_store = deps.task_store
        self.delayed = deps.delayed
        self.dead_letter = deps.dead_letter
        self.drain_timeout = deps.drain_timeout

    
    async def execute(self, task: Task) -> None:
        """Run a task and ACK on success and NACK on failure."""

        logger.info(
            "executing task task_id=%s priority=%d attempt=%d max_attempt=%d",
            task.id, task.priority, task.retries + 1, task.max_retries + 1
        )

        try:
            handler = self.handlers.get(task.type)

            result = await asyncio.wait_for(
                handler(task),
                timeout=self.drain_timeout
            )

            await self.broker.ack(task.id)

            logger.info("task completed task_id=%s detai=%s", task.id, result.detail)
        
        except LeaseNotHeld:
            logger.exception("lease no longer hold task_id=%s", task.id)
        
        except Exception as exc:
            logger.exception("task failed task_id=%s", task.id)
        
            task.error = str(exc) or exc.__class__.__name__
            try:
                await self.broker.nack(task.id)

            except LeaseNotHeld:
                logger.exception("lease no longer held while nacking task_id=%s", task.id)

                return

            await self._handle_failure(task)

    async def _handle_failure(self, task: Task) -> None:
        """Route a failed task to retry or dead letter queue."""

        if task.retries < task.max_retries:
            await self._retry_task(task)
        
        else:
            await self._deadletter(task)
    
    async def _retry_task(self, task: Task) -> None:
        """Increment retry count and schedule the task with exponential backoff time."""

        task.retries += 1
        task.status = TaskStatus.PENDING

        delay = backoff_delay(task.retries)
        execute_at = time.time() + delay

        await self.delayed.schedule_retry(task, execute_at)

        logger.info(
            "task scheduled for retry task_id=%s, retries=%d, max_retries=%d, delay=%ss",
            task.id,
            task.retries,
            task.max_retries,
            int(delay)
        )
    
    async def _deadletter(self, task: Task):
        """Mark an exhausted task failed and push it to the DLQ."""

        task.status = TaskStatus.FAILED

        failed_task = FailedTask(
            task = task.model_copy(),
            failed_at=utc_now(),
            reason = task.error or "maximum retries exhausted"
        )

        await self.dead_letter.push(task, failed_task)

        logger.warning(
            "task moved to dead-letter task_id=%s max_retries=%d",
            task.id, task.max_retries,
        )

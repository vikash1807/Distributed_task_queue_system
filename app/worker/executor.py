# app/worker/executor.py

"""Execute a single claimed task and route it's outcome to ack, retry or DLQ. """

from __future__ import annotations

import asyncio
import logging
import time
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from app.broker import LeaseNotHeld, RedisBroker
from app.handler import Registry
from app.model import Task, TaskStatus, FailedTask, TaskEvent, TaskEventType, WorkerState
from app.queue import DelayedScheduler
from app.store import TaskStore, DeadLetterStore, MetricStore, EventStore, WorkerStateStore



logger = logging.getLogger(__name__)
DEFAULT_DRAIN_TIMEOUT = 5.0  # seconds

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def backoff_delay(retries: int) -> float:
    """
    Returns retry delay for a given (post-increment) retry count: 
    exponential 2^retries seconds, capped at 60s.
    """
    return float(min(2 ** retries, 60))


@dataclass
class ExecutorDeps:
    broker: RedisBroker
    handlers: Registry
    event_store: EventStore
    task_store: TaskStore
    metric_store: MetricStore
    worker_state: WorkerStateStore
    delayed: DelayedScheduler
    dead_letter: DeadLetterStore
    drain_timeout: float = DEFAULT_DRAIN_TIMEOUT


class Executor:
    def __init__(self, deps: ExecutorDeps) -> None:
        self.broker = deps.broker
        self.handlers = deps.handlers

        self.event_store = deps.event_store
        self.metric_store = deps.metric_store
        self.task_store = deps.task_store
        self.worker_state = deps.worker_state

        self.delayed = deps.delayed
        self.dead_letter = deps.dead_letter
        self.drain_timeout = deps.drain_timeout

    
    async def execute(self, task: Task, worker_id: int) -> None:
        """Run a task and ACK on success and NACK on failure."""

        logger.info(
            "executing task task_id=%s priority=%d attempt=%d max_attempt=%d",
            task.id, task.priority, task.retries + 1, task.max_retries + 1
        )

	    # Mark worker state as processing 
        await self.worker_state.set(
            WorkerState(
                id=worker_id,
                status="processing",
                task_id=task.id,
                started_at=utc_now()
            )
        )

        await self._emit_event(
            task_id=task.id,
            event_type=TaskEventType.STARTED, 
            worker_id=worker_id, 
            detail=f"Worker {worker_id} picked up task"
        )

        try:
            # get the handler registered for this type of task.
            # Run the handler with drain_timeout so a shutting down worker don't run forever.
            handler = self.handlers.get(task.type)

            result = await asyncio.wait_for(
                handler(task),
                timeout=self.drain_timeout
            )

            await self.broker.ack(task.id)
            
            # update processed metric count
            await self.metric_store.incr_processed()

            # emit completed Event
            await self._emit_event(
                task_id=task.id,
                event_type=TaskEventType.COMPLETED, 
                worker_id=worker_id, 
                detail=f"task completed succesfully. Result - {result.detail}"
            )

            logger.info("task completed task_id=%s detail=%s", task.id, result.detail)
        
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

            # update failed task metric count
            await self.metric_store.incr_failed()

            # emit failed event
            await self._emit_event(
                task_id=task.id,
                event_type=TaskEventType.FAILED, 
                worker_id=worker_id, 
                detail=task.error
            )

            await self._handle_failure(task, worker_id)

        # Return worker to idle.
        await self.worker_state.set(
            WorkerState(
                id=worker_id,
                status="idle"
            )
        )

    async def _handle_failure(self, task: Task, worker_id: int) -> None:
        """Route a failed task to retry or dead letter queue."""

        if task.retries < task.max_retries:
            await self._retry_task(task, worker_id)
        
        else:
            await self._deadletter(task, worker_id)
    
    async def _retry_task(self, task: Task, worker_id: int) -> None:
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

        # emit event
        await self._emit_event(
            task_id=task.id,
            event_type=TaskEventType.RETRYING, 
            worker_id=worker_id, 
            detail=f"Retry {task.retries}/{task.max_retries} in {int(delay)}s"
        )
        # update retry tasks metric count
        await self.metric_store.incr_retries()
    
    async def _deadletter(self, task: Task, worker_id: int):
        """Mark an exhausted task failed and push it to the DLQ."""

        task.status = TaskStatus.FAILED

        failed_task = FailedTask(
            **task.model_dump(),
            failed_at=utc_now(),
            reason=task.error or "maximum retries exhausted",
        )

        await self.dead_letter.push(failed_task)

        logger.warning(
            "task moved to dead-letter task_id=%s max_retries=%d",
            task.id, task.max_retries,
        )
        
        # emit event
        await self._emit_event(
            task_id=task.id,
            event_type=TaskEventType.DEAD_LETTERED, 
            worker_id=worker_id, 
            detail=f"task moved to dead-letter task_id = {task.id}"
        )

    async def _emit_event(
            self,
            task_id: str,
            event_type: TaskEventType,
            worker_id: int,
            detail: str
        ) -> None:
        event = TaskEvent(
            id=f"evt-{secrets.token_hex(12)}",
            task_id=task_id,
            type=event_type,
            worker_id=worker_id,
            detail=detail,
            timestamp=utc_now(),
        )
        try:
            await self.event_store.push(event)
        except Exception:
            logger.exception("error pushing event for task_id=%s", task_id)


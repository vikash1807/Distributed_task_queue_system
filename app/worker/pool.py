"""Async worker pool for claiming and executing tasks."""

from __future__ import annotations

import asyncio
import logging

from app.broker import RedisBroker
from app.worker.executor import Executor

logger = logging.getLogger(__name__)


class Pool:
    def __init__(
        self,
        broker: RedisBroker,
        executor: Executor,
        worker_count: int,
        poll_interval: float,
    ) -> None:
        
        self.broker = broker
        self.executor = executor
        self.worker_count = worker_count
        self.poll_interval = poll_interval

        self._stop = asyncio.Event()
        self._workers: list[asyncio.Task] = []
    
    async def start(self) -> None:
        """Launch the worker tasks. They run until ``stop`` is called."""
        self._stop.clear()

        self._workers = [
            asyncio.create_task(self._worker(worker_id))
            for worker_id in range(self.worker_count)
        ]

        logger.info(
            "worker pool started count=%d",
            self.worker_count,
        )
    
    async def stop(self) -> None:
        """Signal shutdown and wait for all workers to finish in-flight work."""

        self._stop.set()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        logger.info("worker pool stopped")
    
    async def _worker(self, worker_id: int) -> None:
        """Claim and execute tasks until shutdown."""

        logger.info("worker started worker=%d", worker_id)

        while not self._stop.is_set():
            try:
                task = await self.broker.dequeue()

                if task is None:
                    await asyncio.sleep(self.poll_interval)
                    continue
                    
                await self.executor.execute(task)
            
            except asyncio.CancelledError:
                break

            except Exception:
                logger.exception("worker error worker_id=%d", worker_id)

                await asyncio.sleep(self.poll_interval)
        
        logger.info("worker stopped workd_id = %d", worker_id)

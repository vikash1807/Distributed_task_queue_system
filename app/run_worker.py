# app/run_worker.py

from __future__ import annotations

import asyncio
import logging

from app.broker import RedisBroker
from app.core.config import load_config
from app.core.logging import setup_logging
from app.handler import create_registry
from app.queue import PriorityQueue, DelayedScheduler
from app.store import new_redis, TaskStore, DeadLetterStore
from app.worker import Executor, ExecutorDeps, Pool

setup_logging()
logger = logging.getLogger(__name__)


async def run() -> None:
    config = load_config()

    redis = new_redis(
        addr=config.redis_addr,
        password=config.redis_pass,
        worker_count=config.worker_count
    )

    try:
        # Fail fast if Redis is unavailable. There is no point starting
        # workers or the delayed scheduler without a working Redis connection.
        try:
            await redis.ping()
        except Exception:
            logger.exception("failed to connect to redis: %s", config.redis_addr)
            raise
        
        logger.info("connected to redis: %s", config.redis_addr)

        # Build application dependencies.
        task_store = TaskStore(redis)
        task_queue = PriorityQueue(redis, task_store)

        delayed = DelayedScheduler(redis, task_queue, task_store)
        dead_letter = DeadLetterStore(redis)

        redis_broker = RedisBroker(
            client=redis,
            task_store=task_store,
            queue_ready=task_queue,
            visibility_timeout=config.visibility_timeout,
            node_id="1" # This field is temporary.
        )

        executor = Executor(
            ExecutorDeps(
                broker=redis_broker,
                handlers=create_registry(),
                delayed=delayed,
                task_store=task_store,
                dead_letter=dead_letter,
                drain_timeout=config.drain_timeout
            )
        )

        pool = Pool(
            broker=redis_broker,
            executor=executor,
            worker_count=config.worker_count,
            poll_interval=config.poll_interval
        )

        try:
            await pool.start()

            logger.info("worker process started workers=%s", config.worker_count)
            # Keep the process alive until it receives SIGINT/SIGTERM.
            await asyncio.Event().wait()

        except asyncio.CancelledError:
            # Propagate cancellation after cleanup in finally blocks.
            logger.info("worker process cancellation requested")
            raise
        except Exception:
            logger.exception("worker process failed")
            raise

        finally:
            await pool.stop()
        
    finally:
        await redis.aclose()
        logger.info("redis connection closed")


def main() -> None:
    """Run the worker application."""

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        # Ctrl+C is an expected way to stop the worker process.
        logger.info("worker process interrupted")

if __name__ == "__main__":
    main()
# app/run_worker.py

from __future__ import annotations

import asyncio
import logging

from app.broker import RedisBroker
from app.core.config import load_config
from app.core.logging import setup_logging
from app.handler import create_registry
from app.queue import PriorityQueue
from app.store import new_redis, TaskStore
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
        await redis.ping()
        
        logger.info("connected to redis: %s", config.redis_addr)

        task_store = TaskStore(redis)
        task_queue = PriorityQueue(redis, task_store)

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
                drain_timeout=config.drain_timeout
            )
        )

        pool = Pool(
            broker=redis_broker,
            executor=executor,
            worker_count=config.worker_count,
            poll_interval=config.poll_interval
        )

        await pool.start()

        try:
            await asyncio.Event().wait()
        finally:
            await pool.stop()
        
    finally:
        await redis.close()
        logger.info("redis connection closed")
    
def main() -> None:
    asyncio.run(run())

if __name__ == "__main__":
    main()
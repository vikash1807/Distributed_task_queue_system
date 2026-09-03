from __future__ import annotations

import logging
import sys
from typing import Optional

import redis.asyncio as redis


logger = logging.getLogger(__name__)


KEY_READY = "taskqueue:ready" # ZSET, score = -priority (higher priority pops first)
KEY_READY_SIGNAL = "taskqueue:ready:signal"
KEY_DELAYED = "taskqueue:delayed"  # ZSET, score = execute-at (unix seconds)
KEY_PROCESSING = "taskqueue:processing"  # ZSET, score = lease deadline (ms)
KEY_DEADLETTER = "taskqueue:deadletter" # LIST of failedTask
KEY_METRICS = "taskqueue:metrics"  # HASH of counters
KEY_NODES = "taskqueue:nodes"  # SET of known node IDs


# Task records live under this prefix : taskqueue:task:{id} (HASH)
KEY_TASK_PREFIX = "taskqueue:task:"


def key_task(task_id: str) -> str:
    """Return the HASH key holding a task's canonical record."""
    return KEY_TASK_PREFIX + task_id


def node_tasks_key(node_id: str) -> str:
    """SET key holding the task IDs a node currently leases."""
    return f"taskqueue:node:{node_id}:tasks"


def new_redis(
    addr: str,
    password: str, 
    worker_count: int,
) -> redis.Redis:
    
    host, _, port = addr.rpartition(":")
    if not host:  # addr had no ':' — treat the whole thing as the host
        host, port = addr, "6379"

    return redis.Redis(
        host=host or "localhost",
        port=int(port or "6379"),
        password=password or None,
        db=0,
        max_connections=worker_count, # + POOL_HEADROOM,
        decode_responses=True,
    )


# app/broker/broker.py

"""
Lease-based broker

``dequeue`` atomically moves a task from the ready set into a processing set with a visibility timeout (lease deadline), stamping this node's ID as owner. 
``ack``/``nack`` release the lease with owner-fencing (a worker whose lease already expired cannot clobber a task re-leased elsewhere); 
the reaper reclaims expired leases. 
Every multi-step mutation is a single Lua script so a crash mid-mutation can never lose or double-book a task.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import redis.asyncio as redis

from app.model import Task, TaskNotFound
from app.queue import PriorityQueue
from app.store import (
    TaskStore,
    KEY_READY,
    KEY_PROCESSING,
    KEY_TASK_PREFIX,
    key_task,
    node_tasks_key,
)

SCRIPTS_DIR = Path(__file__).parent / "scripts"


def load_script(name: str) -> str:
    """Read a Lua script from the broker's scripts directory."""
    return (SCRIPTS_DIR / name).read_text(encoding="utf-8")


class LeaseNotHeld(Exception):
    """Raised when a node tries to modify a task it does not currently own."""


class RedisBroker:
    """
    The Redis-backed broker. Each instance belongs to one node; its ``node_id`` is stamped on every task it leases so the reaper can reclaim this node's work if
    it dies, and so ack/nack can fence against a lease re-leased elsewhere.
    
    Each Broker instance represents one worker node. The node ID is stored as the owner of tasks claimed by this broker.

    The broker uses four Lua scripts:

    - dequeue.lua: atomically claims a task from `ready`
    - ack.lua: completes an owned task
    - nack.lua: releases an owned task
    - extend.lua: extends an active lease

    All operations that modify lease state are delegated to Redis Lua scripts so the individual Redis mutations happen atomically.
    """

    def __init__(
        self,
        client: redis.Redis,
        task_store: TaskStore,
        queue_ready: PriorityQueue,
        visibility_timeout: float,
        node_id: str,
    ) -> None:
        self.client = client
        self.task_store = task_store
        self.queue_ready = queue_ready

        self.visibility_timeout = visibility_timeout
        self.node_id = node_id

        # Register Lua scripts once when the broker is created.
        self._dequeue = client.register_script(load_script("dequeue.lua"))
        self._ack = client.register_script(load_script("ack.lua"))
        self._nack = client.register_script(load_script("nack.lua"))
        self._extend = client.register_script(load_script("extend.lua"))

    def _lease_deadline(self) -> int:
        """Return the lease deadline as Unix time in milliseconds."""
        return int(
            (time.time() + self.visibility_timeout) * 1000
        )
    
    async def enqueue(self, task: Task):
        """Persist a task and place it in ready queue.
        """
        await self.task_store.save(task)
        await self.queue_ready.enqueue(task)
    
    async def dequeue(self) -> Optional[Task]:
        """
        Atomically claim next ready task from queue
        The Lua script removes the task from `ready`, creates its lease in `processing`, records this node as the owner, and adds the task to this node's task set.

        Returns:
            The claimed Task, or None when the ready queue is empty.
        """
        deadline = self._lease_deadline

        result = await self._dequeue_script(
            keys=[
                KEY_READY,
                KEY_PROCESSING,
                KEY_TASK_PREFIX,
                node_tasks_key(self.node_id),
            ],
            args=[
                str(deadline),
                self.node_id,
            ],
        )

        if result is None:
            return None

        task_id = result.decode() if isinstance (result, bytes) else str(result)

        try:
            return await self.task_store.get(task_id)
        except TaskNotFound:
            # The queue contained an ID whose task record disappeared.
            await self.client.zrem(KEY_PROCESSING, task_id)
            return None
    
    async def ack(self, task_id: str):
        """
        Acknowledge a successfully completed task.

        The Lua script verifies that this broker still owns the lease
        before changing the task state.

        Raises:
            LeaseNotHeld: if this node does not own the lease.
        """
        result = await self._ack_script(
            keys=[
                KEY_PROCESSING,
                key_task(task_id),
                node_tasks_key(self.node_id),
            ],
            args=[
                task_id,
                self.node_id,
            ],
        )
        if int(result) == 0:
            raise LeaseNotHeld(task_id)
    
    async def nack(self, task_id: str) -> None:
        """
        Release a task that could not be completed.
        Owner fencing is performed by the Lua script.

        Raises:
            LeaseNotHeld: if this node does not own the lease.
        """
        result = await self._nack_script(
            keys=[
                KEY_PROCESSING,
                key_task(task_id),
                node_tasks_key(self.node_id),
            ],
            args=[
                task_id,
                self.node_id,
            ],
        )
        if int(result) == 0:
                    raise LeaseNotHeld(task_id)

    async def extend_lease(
        self,
        task_id: str,
        extension: float,
    ) -> None:
        """
        Extend the visibility timeout of a leased task.

        The existence check and deadline update are performed together
        by the Lua script.

        Raises:
            LeaseNotHeld: if the task is no longer leased.
        """
        deadline = int(
            (time.time() + extension) * 1000
        )

        result = await self._extend_script(
            keys=[KEY_PROCESSING],
            args=[
                task_id,
                str(deadline),
            ],
        )
        if int(result) == 0:
                    raise LeaseNotHeld(task_id)

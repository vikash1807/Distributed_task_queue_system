# app/handlers/registry.py
"""
Maps a task's ``type`` to the coroutine that executes it, so workers run heterogeneous task types.The registry is read-only after startup, so no locking is needed for concurrent dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from app.model import Task


class NoHandler(Exception):
    """Raised when no handler is registered for a task type."""


TYPE_SLEEP = "sleep"
TYPE_HTTP_FETCH = "http_fetch"
TYPE_HASH = "hash"


@dataclass
class Result:
    """Successful result returned by a task handler."""
    detail: str = ""

# A handler execute a single task, returning a Result or raising a signal failure.
Handler = Callable[[Task], Awaitable[Result]]


class Registry:
    """Maps task types to their async handlers."""

    def __init__(self):
        self._handlers : dict[str, Handler] = {}
    
    def register(self, task_type: str, handler: Handler) -> None:
        """
        Register associates a handler with task type. A second registeration for the same overwrites the first.
        """
        self._handlers[task_type] = handler
    
    def get(self, task_type: str) -> Handler:
        """Return the handler for a task type defaulting to sleep."""
        handler = self._handlers.get(task_type or "sleep")

        if handler is None:
            raise NoHandler(f"No handler registered for the task type {task_type}")

        return handler


def create_registry() -> Registry:
    """Create a registry containing the built-in task handlers."""

    from app.handler.builtins import hash_task, http_fetch, sleep

    registry = Registry()
    registry.register(TYPE_SLEEP, sleep)
    registry.register(TYPE_HTTP_FETCH, http_fetch)
    registry.register(TYPE_HASH, hash_task)

    return registry



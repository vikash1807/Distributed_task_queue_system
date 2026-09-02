# app/model/task.py

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel


class TaskNotFound(Exception):
    """Raised by ``TaskStore.get`` when no record exists for the given id."""


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def parse_status(s: str) -> TaskStatus:
    """Parse a status string, defaulting to PENDING for empty/unknown values."""
    try:
        return TaskStatus(s or "pending")
    except ValueError:
        return TaskStatus.PENDING


class Task(BaseModel):
    id: str = ""
    type: str = ""
    payload: dict[str, Any] | None = None
    priority: int = 0
    delay: int = 0
    max_retries: int = 0  # 0 = no retries
    retries: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    error: str = ""
    owner: str = ""  # node ID currently leasing the task

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}

        d["id"] = self.id

        if self.type:  # omit empty
            d["type"] = self.type
        if self.payload is not None:  # omit empty
            d["payload"] = self.payload

        d["priority"] = self.priority
        d["delay"] = self.delay
        d["max_retries"] = self.max_retries
        d["retries"] = self.retries
        d["status"] = self.status.value
        d["created_at"] = self.created_at

        if self.error:  # omit empty
            d["error"] = self.error
        if self.owner:  # omit empty
            d["owner"] = self.owner
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Task":
        return cls(
            id=d.get("id", ""),
            type=d.get("type", ""),
            payload=d.get("payload"),
            priority=int(d.get("priority", 0) or 0),
            delay=int(d.get("delay", 0) or 0),
            max_retries=int(d.get("max_retries", 0) or 0),
            retries=int(d.get("retries", 0) or 0),
            status=parse_status(d.get("status", "pending")),
            created_at=d.get("created_at"),
            error=d.get("error", ""),
            owner=d.get("owner", ""),
        )

class Metrics(BaseModel):
    total_processed: int = 0
    total_failed: int = 0
    total_retries: int = 0
    queue_size: int = 0
    active_workers: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "total_retries": self.total_retries,
            "queue_size": self.queue_size,
            "active_workers": self.active_workers,
        }

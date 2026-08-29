# app/api/schema.py

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SubmitTaskRequest(BaseModel):
    id: str = ""
    type: str = ""
    payload: Any = None
    priority: int = 0
    delay: int = 0
    max_retries: int = 0
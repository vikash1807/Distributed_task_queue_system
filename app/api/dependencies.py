# app/api/dependencies.py

from __future__ import annotations

from fastapi import Request

from app.container import AppContainer
from app.service.task import TaskService


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)

    if container is None:
        raise RuntimeError("application container is not initialized")

    return container


def get_task_service(request: Request) -> TaskService:
    return get_container(request).task_service

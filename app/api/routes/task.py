from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_task_service
from app.api.schema import SubmitTaskRequest
from app.model import TaskNotFound
from app.service.task import DuplicateTaskError, TaskService


logger = logging.getLogger(__name__)


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        content={"error": message},
        status_code=status_code,
    )


def create_task_routes() -> APIRouter:
    router = APIRouter(prefix="/tasks")

    @router.post("")
    async def submit_task(
        request: SubmitTaskRequest,
        task_service: TaskService = Depends(get_task_service),
    ) -> Response:
        try:
            task = await task_service.submit_task(
                id=request.id,
                type=request.type,
                payload=request.payload,
                priority=request.priority,
                delay=request.delay,
                max_retries=request.max_retries,
            )
        except DuplicateTaskError:
            return error_response(
                409,
                f'task with id "{request.id}" already exists',
            )
        except Exception:
            logger.exception("failed to submit task")
            return error_response(500, "failed to submit task")

        return JSONResponse(
            content=jsonable_encoder(task.to_dict()),
            status_code=201,
        )

    @router.get("/{task_id}")
    async def get_task(
        task_id: str,
        task_service: TaskService = Depends(get_task_service),
    ) -> Response:
        try:
            task = await task_service.get_task(task_id)
        except TaskNotFound:
            return error_response(404, "task not found")
        except Exception:
            logger.exception("failed to retrieve task id=%s", task_id)
            return error_response(500, "failed to retrieve task")

        return JSONResponse(
            content=jsonable_encoder(task.to_dict()),
            status_code=200,
        )

    return router

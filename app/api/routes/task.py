# app/api/routes/task.py

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
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

    @router.get("/failed")
    async def get_failed_tasks(
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=0), 
        task_service: TaskService = Depends(get_task_service)
    ) -> Response:

        try:
            failed_tasks = await task_service.get_failed_tasks(offset, limit)

            return JSONResponse(
                content = [
                    failed_task.to_dict()
                    for failed_task in failed_tasks
                ],
                status_code=200,
            )
        
        except Exception:
            logger.exception("Failed to get dead-letter tasks")
            return error_response(500, "Failed to get dead-letter tasks")
    
    @router.get("/failed/redrive")
    async def redrive_failed_tasks(
        task_service: TaskService = Depends(get_task_service)
    ) -> Response:
        try:
            result = await task_service.redrive_failed_tasks()
        
            return JSONResponse(
                content=result,
                status_code=200,
            )

        except Exception:
            logger.exception("failed to redrive dead-letter tasks")
            return error_response(500, "failed to redrive dead-letter tasks")

    return router

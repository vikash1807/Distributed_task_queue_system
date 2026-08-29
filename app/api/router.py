# app/api/router.py

from __future__ import annotations


from fastapi import APIRouter, FastAPI

from app.api.middleware import (
    CorsMiddleware,
    ExceptionRecoveryMiddleware,
    RequestLoggingMiddleware,
)
from app.api.routes.task import create_task_routes


def create_api_router() -> APIRouter:
    api_router = APIRouter(prefix="/api")
    api_router.include_router(create_task_routes())

    return api_router


def configure_api(application: FastAPI) -> None:
    """
    Configure API routes and HTTP middleware for the application.
    """

    application.include_router(create_api_router())

    application.add_middleware(CorsMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(ExceptionRecoveryMiddleware)

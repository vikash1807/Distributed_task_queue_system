# app/api/routes/events.py

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_event_service
from app.service import EventService


logger = logging.getLogger(__name__)


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        content={"error": message},
        status_code=status_code,
    )


def create_event_routes() -> APIRouter:

    router = APIRouter(prefix="/events", tags=["events"])

    @router.get("")
    async def get_events(
        limit: int = Query(default=50, ge=0, le=200),
        service: EventService = Depends(get_event_service), 
    ) -> Response:
        try:
            events = await service.list_events(limit)
        except Exception:
            logger.exception("failed to retrieve events.")
            return error_response(500, "failed to retrieve events.")
        
        return JSONResponse(
            content=[event.model_dump(mode="json") for event in events],
            status_code=200,
        )
    
    @router.get("/cluster")
    async def get_cluster_events(
        limit: int = Query(default=50, ge=0, le=200),
        service: EventService = Depends(get_event_service), 
    ) -> Response:
        try:
            events = await service.list_cluster_events(limit)
        except Exception:
            logger.exception("failed to retrieve cluster events.")
            return error_response(500, "failed to retrieve cluster events.")
        
        return JSONResponse(
            content=[event.model_dump() for event in events],
            status_code=200,
        )
    
    return router
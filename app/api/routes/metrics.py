# app/api/routes/metrics.py

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import get_metrics_service
from app.service import MetricService


logger = logging.getLogger(__name__)


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        content={"error": message},
        status_code=status_code,
    )


def create_metrics_routes() -> APIRouter:

    router = APIRouter(prefix="/metrics", tags=["metrics"])

    @router.get("")
    async def get_metrics(
        service: MetricService = Depends(get_metrics_service), 
    ) -> Response:
        try:
            metrics = await service.get_metrics()
        except Exception:
            logger.exception("failed to retrieve metrics.")
            return error_response(500, "failed to retrieve metrics.")
        
        return JSONResponse(
            content=jsonable_encoder(metrics.to_dict()),
            status_code=200,
        )
    
    @router.get("/enhanced")
    async def get_enhanced_metrics(
        service: MetricService = Depends(get_metrics_service), 
    ) -> Response:
        try:
            enhanced_metrics = await service.get_enhanced_metrics()
        except Exception:
            logger.exception("failed to retrieve enhanced metrics.")
            return error_response(500, "failed to retrieve enhanced metrics.")
        
        return JSONResponse(
            content=jsonable_encoder(enhanced_metrics.to_dict()),
            status_code=200,
        )
    
    return router
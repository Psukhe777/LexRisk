"""backend/routers/health.py — liveness and configuration probe."""

from fastapi import APIRouter, Depends

import db_utils
from backend.config import Settings, get_settings
from backend.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        database="connected" if db_utils._connection_pool is not None else "unavailable",
        llm_configured=settings.has_llm_key,
    )

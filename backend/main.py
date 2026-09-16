"""
backend/main.py — LexRisk REST API (Session 1 bootstrap).

Run locally:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Scope of this session: app factory, CORS for the PWA client, health probe and
the analysis endpoints wrapping the existing engine. Auth (Session 3) and Stripe
billing (Session 4) mount onto this same app.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.config import get_settings
from backend.routers import analysis, health
from db_utils import init_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.database_url:
        init_db_pool(settings.database_url)
    else:
        logger.warning("DATABASE_URL not set - quota and cache features are disabled")
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Send the preview root to the interactive API docs."""
        return RedirectResponse(url="/docs")

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(analysis.router, prefix=settings.api_prefix)

    return app


app = create_app()

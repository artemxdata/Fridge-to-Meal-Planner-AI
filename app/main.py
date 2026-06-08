from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v2 import router as v2_router
from app.api.v3 import router as v3_router
from app.catalog import recipes
from app.config import settings
from app.db import check_database, create_schema
from app.schemas import HealthResponse

logger = logging.getLogger("fridge_to_meal")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_tables:
        await create_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Human-controlled pantry and meal-planning assistant.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    react_assets_path = settings.react_frontend_dist_path / "assets"
    if react_assets_path.exists():
        app.mount("/assets", StaticFiles(directory=react_assets_path), name="pwa-assets")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
            request_id,
        )
        return response

    @app.get("/")
    def root() -> dict:
        return {
            "ok": True,
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "app": "/app",
            "pwa": "/pwa",
            "recipes": len(recipes()),
        }

    @app.get("/health/live", response_model=HealthResponse, tags=["Health"])
    def live() -> HealthResponse:
        return HealthResponse(status="ok", version=settings.app_version, environment=settings.environment)

    @app.get("/health/ready", response_model=HealthResponse, tags=["Health"])
    async def ready() -> HealthResponse:
        if not recipes():
            raise HTTPException(503, "Recipe catalog is empty")
        await check_database()
        return HealthResponse(status="ready", version=settings.app_version, environment=settings.environment)

    @app.get("/app", include_in_schema=False)
    def frontend() -> FileResponse:
        if not settings.frontend_path.exists():
            raise HTTPException(404, "index.html not found")
        return FileResponse(settings.frontend_path)

    @app.get("/pwa", include_in_schema=False)
    @app.get("/pwa/{path:path}", include_in_schema=False)
    def react_frontend(path: str = "") -> FileResponse:
        if not settings.react_frontend_path.exists():
            raise HTTPException(404, "React build not found. Run npm run build in frontend/.")
        return FileResponse(settings.react_frontend_path)

    app.include_router(v2_router)
    app.include_router(v3_router)
    return app


app = create_app()

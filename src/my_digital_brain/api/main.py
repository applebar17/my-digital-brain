from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from my_digital_brain.api.routes.chat import router as chat_router
from my_digital_brain.api.routes.debug import router as debug_router
from my_digital_brain.api.routes.graph import router as graph_router
from my_digital_brain.api.routes.health import router as health_router
from my_digital_brain.api.routes.telegram import router as telegram_router
from my_digital_brain.config import get_settings
from my_digital_brain.graph.owner import OwnerNodeManager
from my_digital_brain.graph.repository import GraphRepository
from my_digital_brain.logging import configure_logging
from my_digital_brain.storage.graph import GraphClient


def initialize_owner() -> None:
    settings = get_settings()
    last_error: Exception | None = None
    for attempt in range(settings.owner_bootstrap_max_attempts):
        try:
            with GraphClient.from_settings(settings) as client:
                OwnerNodeManager(GraphRepository(client), settings).ensure_owner()
            return
        except Exception as exc:
            last_error = exc
            if attempt + 1 < settings.owner_bootstrap_max_attempts:
                time.sleep(settings.owner_bootstrap_retry_delay_seconds)
    assert last_error is not None
    raise last_error


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    initialize_owner()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_dir=settings.log_dir,
        app_level=settings.app_log_level,
        agentic_level=settings.agentic_log_level,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
        truncate_on_start=settings.log_truncate_on_start,
    )

    app = FastAPI(title="My Digital Brain", version="0.1.0", lifespan=lifespan)
    cors_origins = settings.frontend_cors_origin_list
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(graph_router)
    app.include_router(chat_router)
    app.include_router(debug_router)
    app.include_router(telegram_router)
    return app


app = create_app()

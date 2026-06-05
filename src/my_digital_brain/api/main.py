from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from my_digital_brain.api.routes.chat import router as chat_router
from my_digital_brain.api.routes.debug import router as debug_router
from my_digital_brain.api.routes.graph import router as graph_router
from my_digital_brain.api.routes.health import router as health_router
from my_digital_brain.api.routes.telegram import router as telegram_router
from my_digital_brain.config import get_settings
from my_digital_brain.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_dir=settings.log_dir,
        app_level=settings.app_log_level,
        agentic_level=settings.agentic_log_level,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )

    app = FastAPI(title="My Digital Brain", version="0.1.0")
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

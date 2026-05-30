from __future__ import annotations

from fastapi import FastAPI

from my_digital_brain.api.routes.graph import router as graph_router
from my_digital_brain.api.routes.health import router as health_router
from my_digital_brain.config import get_settings
from my_digital_brain.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="My Digital Brain", version="0.1.0")
    app.include_router(health_router)
    app.include_router(graph_router)
    return app


app = create_app()

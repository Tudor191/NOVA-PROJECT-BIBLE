"""nova_planning_engine's FastAPI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_planning_engine.api.health import router as health_router
from nova_planning_engine.config import Settings
from nova_planning_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_planning_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS

logger = get_logger("planning-engine")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_observability("planning-engine", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="planning-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("planning-engine starting")
        await bus.connect()
        app.state.bus = bus
        app.state.ready = True
        yield
        logger.info("planning-engine shutting down")
        app.state.ready = False
        await bus.close()

    fastapi_app = FastAPI(title="planning-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

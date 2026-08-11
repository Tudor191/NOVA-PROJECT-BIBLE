"""digital-twin-engine's FastAPI entrypoint -- wires `DigitalTwinRepository`
and the Event Bus to their concrete implementations, and registers
`communication.session.completed` (subscribe) and `digital_twin.
preferences.get.request` (serve), the two Event-Bus subjects declared in
`events/subscribed.py` (docs/design/phase-2d/06-personal-companion.md
Sec7.1).

Publishes nothing yet (`events/published.py`'s own module docstring) --
`personality.memory.update` awaits an approved evidence source (Fork F) and
`communication.intent.deliver.request` is Step 9's own scope -- but the
outbox/worker infrastructure is wired from day one regardless (Priority 1's
precedent, docs/design/phase-2d/05-conversation-intelligence-closure.md
Sec3.5), so Step 9 only has to enqueue into an already-running dispatch
loop, not build one.

`create_app` accepts `repository` as an optional override so tests can
inject a fake without needing real Postgres reachable -- real infra is only
constructed when it isn't supplied (mirrors every other engine's `main.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_digital_twin_engine.api.preferences import router as preferences_router
from nova_digital_twin_engine.api.proactive_policy import router as proactive_policy_router
from nova_digital_twin_engine.api.profile import router as profile_router
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.domain.ports import DigitalTwinRepository
from nova_digital_twin_engine.events.handlers import (
    make_preferences_get_handler,
    make_session_completed_handler,
)
from nova_digital_twin_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_digital_twin_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_digital_twin_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("digital-twin-engine")


def create_app(
    settings: Settings | None = None,
    *,
    repository: DigitalTwinRepository | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("digital-twin-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = bind_event_bus(
        "digital-twin-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("digital-twin-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_digital_twin_engine.repository.postgres_digital_twin_repository import (
                PostgresDigitalTwinRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresDigitalTwinRepository(session_factory)

        app.state.settings = settings
        app.state.repository = repo
        app.state.bus = bus
        app.state.metrics = metrics

        await bus.connect()
        await bus.subscribe(
            "communication.session.completed", make_session_completed_handler(app)
        )
        await bus.serve(
            "digital_twin.preferences.get.request",
            make_preferences_get_handler(app),
            source_engine="digital-twin-engine",
        )
        app.state.ready = True
        yield
        logger.info("digital-twin-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="digital-twin-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(profile_router)
    fastapi_app.include_router(preferences_router)
    fastapi_app.include_router(proactive_policy_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

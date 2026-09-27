"""nova_cognitive_state_engine's FastAPI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_cognitive_state_engine.api.cognitive_state import router as cognitive_state_router
from nova_cognitive_state_engine.api.health import router as health_router
from nova_cognitive_state_engine.clients.decision_trigger_client import DecisionTriggerClient
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.domain.ports import DecisionTriggerPort
from nova_cognitive_state_engine.events.handlers import (
    SENSOR_HEALTH_SUBJECT,
    make_sensor_health_handler,
)
from nova_cognitive_state_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_cognitive_state_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
        PostgresCognitiveStateRepository,
    )

logger = get_logger("cognitive-state-engine")


def create_app(
    settings: Settings | None = None,
    *,
    trigger: DecisionTriggerPort | None = None,
    repository: PostgresCognitiveStateRepository | None = None,
) -> FastAPI:
    """`repository` is an optional override so a test can hand in one bound to a
    real test database -- real infrastructure is constructed only when it is not
    supplied, the same convention as every other engine's `main.py`."""
    settings = settings or Settings()
    configure_observability("cognitive-state-engine", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="cognitive-state-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("cognitive-state-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_cognitive_state_engine.repository.postgres_cognitive_state_repository import (
                PostgresCognitiveStateRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            repo = PostgresCognitiveStateRepository(create_session_factory(engine))

        await bus.connect()
        app.state.bus = bus
        app.state.settings = settings
        app.state.repository = repo

        # Phase 4F.6: the trigger port `promotion_orchestration.promote_thought`
        # sends through, bound to the same allow-listed bus so a subject
        # outside `PUBLISHABLE_SUBJECTS` fails at the boundary, not in the
        # adapter. Nothing in this engine's running topology calls
        # `promote_thought` yet -- that surface is 4F.7's -- so no repository
        # or database engine is opened here either (CF-11 stays OPEN).
        #
        # (Clarified 2026-09-26, Phase 4F.7 -- TDD 4F §24 RS-1b, RS-1c, RS-11.
        # The comment above is preserved as written, and two of its claims no
        # longer hold. "That surface is 4F.7's" is superseded: 4F.7 is strictly
        # read-only and does not call `promote_thought`; the production
        # promotion driver belongs to the promotion slice 4F.P. And a repository
        # and database engine *are* now opened above -- for 4F.7's read surface
        # and its sensor-state subscription, never for promotion. Still true:
        # nothing in this engine's running topology calls `promote_thought`, and
        # CF-11 stays OPEN.)
        app.state.trigger = trigger or DecisionTriggerClient(
            bus, timeout_seconds=settings.decision_trigger_timeout_seconds
        )

        # Phase 4F.7 (RS-3a): the one subscription. Registered before readiness,
        # so a ready engine is a listening one. Core NATS: a report dispatched
        # before this line runs is not delivered here (TDD 4F.7 §15 K-1).
        await bus.subscribe(SENSOR_HEALTH_SUBJECT, make_sensor_health_handler(repo))

        app.state.ready = True
        yield
        logger.info("cognitive-state-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="cognitive-state-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(cognitive_state_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

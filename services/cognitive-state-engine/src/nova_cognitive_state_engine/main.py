"""nova_cognitive_state_engine's FastAPI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_cognitive_state_engine.api.health import router as health_router
from nova_cognitive_state_engine.clients.decision_trigger_client import DecisionTriggerClient
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.domain.ports import DecisionTriggerPort
from nova_cognitive_state_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_cognitive_state_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS

logger = get_logger("cognitive-state-engine")


def create_app(
    settings: Settings | None = None,
    *,
    trigger: DecisionTriggerPort | None = None,
) -> FastAPI:
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
        await bus.connect()
        app.state.bus = bus
        app.state.settings = settings

        # Phase 4F.6: the trigger port `promotion_orchestration.promote_thought`
        # sends through, bound to the same allow-listed bus so a subject
        # outside `PUBLISHABLE_SUBJECTS` fails at the boundary, not in the
        # adapter. Nothing in this engine's running topology calls
        # `promote_thought` yet -- that surface is 4F.7's -- so no repository
        # or database engine is opened here either (CF-11 stays OPEN).
        app.state.trigger = trigger or DecisionTriggerClient(
            bus, timeout_seconds=settings.decision_trigger_timeout_seconds
        )
        app.state.ready = True
        yield
        logger.info("cognitive-state-engine shutting down")
        app.state.ready = False
        await bus.close()

    fastapi_app = FastAPI(title="cognitive-state-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

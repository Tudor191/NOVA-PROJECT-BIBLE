"""communication-engine's FastAPI entrypoint -- wires `CommunicationRepository`,
the three upstream ports (`PersonalityPort`, `ModelOrchestrationPort`,
`WorldModelPort`), the `SessionRegistry`, and the Event Bus to their
concrete implementations; registers the three served RPCs declared in
`events/subscribed.py`; and runs design doc Sec3.5's restart recovery pass
at startup.

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres/a real Event Bus RPC round trip reachable
-- real infra is only constructed for whichever port isn't supplied (mirrors
every other engine's `main.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_communication_engine.api.health import router as health_router
from nova_communication_engine.api.notifications import router as notifications_router
from nova_communication_engine.api.sessions import router as sessions_router
from nova_communication_engine.api.websocket import router as websocket_router
from nova_communication_engine.config import Settings
from nova_communication_engine.domain import session_lifecycle
from nova_communication_engine.domain.ports import (
    CommunicationRepository,
    ModelOrchestrationPort,
    PersonalityPort,
    WorldModelPort,
)
from nova_communication_engine.events.handlers import (
    make_intent_deliver_handler,
    make_session_close_handler,
    make_session_create_handler,
)
from nova_communication_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_communication_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_communication_engine.observability import create_metrics
from nova_communication_engine.session_registry import SessionRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("communication-engine")


def create_app(
    settings: Settings | None = None,
    *,
    repository: CommunicationRepository | None = None,
    personality_port: PersonalityPort | None = None,
    model_orchestration_port: ModelOrchestrationPort | None = None,
    world_model_port: WorldModelPort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("communication-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="communication-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("communication-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_communication_engine.repository.db import (
                create_engine,
                create_session_factory,
            )
            from nova_communication_engine.repository.postgres_communication_repository import (
                PostgresCommunicationRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresCommunicationRepository(session_factory)

        personality = personality_port
        if personality is None:
            from nova_communication_engine.clients.personality_client import PersonalityClient

            personality = PersonalityClient(
                bus, timeout_ms=settings.communication_engine_personality_rpc_timeout_ms
            )

        model_orchestration = model_orchestration_port
        if model_orchestration is None:
            from nova_communication_engine.clients.model_orchestration_client import (
                ModelOrchestrationClient,
            )

            model_orchestration = ModelOrchestrationClient(
                bus,
                transcribe_timeout_ms=settings.communication_engine_transcribe_rpc_timeout_ms,
                synthesize_timeout_ms=settings.communication_engine_synthesize_rpc_timeout_ms,
            )

        world_model = world_model_port
        if world_model is None:
            from nova_communication_engine.clients.world_model_client import WorldModelClient

            world_model = WorldModelClient(
                bus, timeout_ms=settings.communication_engine_world_model_rpc_timeout_ms
            )

        await bus.connect()
        await bus.serve(
            "communication.intent.deliver.request",
            make_intent_deliver_handler(app),
            source_engine="communication-engine",
        )
        await bus.serve(
            "communication.session.create.request",
            make_session_create_handler(app),
            source_engine="communication-engine",
        )
        await bus.serve(
            "communication.session.close.request",
            make_session_close_handler(app),
            source_engine="communication-engine",
        )

        app.state.settings = settings
        app.state.repository = repo
        app.state.personality_port = personality
        app.state.model_orchestration_port = model_orchestration
        app.state.world_model_port = world_model
        app.state.session_registry = SessionRegistry()
        app.state.bus = bus
        app.state.metrics = metrics

        # Design doc Sec3.5: restart recovery -- no channel connection can
        # possibly be live yet at this point, so every non-terminal session
        # becomes Paused.
        for stale_session in await repo.list_non_terminal_sessions():
            await session_lifecycle.recover_session_to_paused(
                session=stale_session, repository=repo, correlation_id=uuid4()
            )

        app.state.ready = True
        yield
        logger.info("communication-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="communication-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(sessions_router)
    fastapi_app.include_router(notifications_router)
    fastapi_app.include_router(websocket_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

"""reasoning-engine's FastAPI entrypoint -- wires every port (`MemoryPort`,
`KnowledgePort`, `WorldModelPort`, `PersonalContextPort`, `GoalsPort`,
`ModelOrchestrationPort`, `ReasoningRepository`, the Event Bus) to their
concrete implementations, and registers `reasoning.reason.request`, the one
served RPC declared in `events/subscribed.py`. `workers/__init__.py` wires
the same ports for the separate Arq worker process (docs/architecture/03-
backend-architecture.md §2's embedded-vs-standalone distinction, applied to
workers).

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres reachable -- real infra is only
constructed for whichever port isn't supplied (mirrors every other engine's
`main.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_reasoning_engine.api.decisions import router as decisions_router
from nova_reasoning_engine.api.reason import router as reason_router
from nova_reasoning_engine.api.traces import router as traces_router
from nova_reasoning_engine.clients.goals_client import GoalsClient
from nova_reasoning_engine.clients.knowledge_client import KnowledgeClient
from nova_reasoning_engine.clients.memory_client import MemoryClient
from nova_reasoning_engine.clients.model_orchestration_client import ModelOrchestrationClient
from nova_reasoning_engine.clients.personal_context_client import PersonalContextClient
from nova_reasoning_engine.clients.world_model_client import WorldModelClient
from nova_reasoning_engine.config import Settings
from nova_reasoning_engine.domain.ports import (
    GoalsPort,
    KnowledgePort,
    MemoryPort,
    ModelOrchestrationPort,
    PersonalContextPort,
    ReasoningRepository,
    WorldModelPort,
)
from nova_reasoning_engine.events.handlers import make_reason_request_handler
from nova_reasoning_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_reasoning_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_reasoning_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("reasoning-engine")


def create_app(
    settings: Settings | None = None,
    *,
    memory_port: MemoryPort | None = None,
    knowledge_port: KnowledgePort | None = None,
    world_model_port: WorldModelPort | None = None,
    personal_context_port: PersonalContextPort | None = None,
    goals_port: GoalsPort | None = None,
    model_orchestration_port: ModelOrchestrationPort | None = None,
    repository: ReasoningRepository | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("reasoning-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = bind_event_bus(
        "reasoning-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("reasoning-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_reasoning_engine.repository.postgres_reasoning_repository import (
                PostgresReasoningRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresReasoningRepository(session_factory)

        world_model = world_model_port or WorldModelClient(bus)

        memory = memory_port or MemoryClient(bus)
        knowledge = knowledge_port or KnowledgeClient(bus)
        personal_context = personal_context_port or PersonalContextClient(world_model)
        goals = goals_port or GoalsClient()
        model_orchestration = model_orchestration_port or ModelOrchestrationClient(bus)

        await bus.connect()
        await bus.serve(
            "reasoning.reason.request",
            make_reason_request_handler(app),
            source_engine="reasoning-engine",
        )

        app.state.settings = settings
        app.state.memory_port = memory
        app.state.knowledge_port = knowledge
        app.state.world_model_port = world_model
        app.state.personal_context_port = personal_context
        app.state.goals_port = goals
        app.state.model_orchestration_port = model_orchestration
        app.state.repository = repo
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.ready = True
        yield
        logger.info("reasoning-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="reasoning-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(reason_router)
    fastapi_app.include_router(traces_router)
    fastapi_app.include_router(decisions_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

"""nova_planning_engine's FastAPI entrypoint -- also constructs
`ModelOrchestrationClient` (ADR-020's sole legal channel to any model) and
the Postgres repository, registers `reasoning.process.completed` (fire-and-
forget subscription) and `planning.decompose.request` (the RPC this engine
serves), and mounts `/v1/plans` (TDD 3B §5, `phase-3b-planning-persistence`
precursor).

`create_app` accepts `repository`/`model_orchestration_port` as optional
overrides so tests can inject fakes without needing real Postgres/event-bus
reachable -- mirrors `action-engine`'s own `main.py` precedent exactly."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_planning_engine.api.health import router as health_router
from nova_planning_engine.api.plans import router as plans_router
from nova_planning_engine.clients.model_orchestration_client import ModelOrchestrationClient
from nova_planning_engine.config import Settings
from nova_planning_engine.domain.ports import ModelOrchestrationPort, PlanningRepository
from nova_planning_engine.events.decompose_handler import make_decompose_request_handler
from nova_planning_engine.events.goals_handler import make_goals_current_request_handler
from nova_planning_engine.events.handlers import make_reasoning_process_completed_handler
from nova_planning_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_planning_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_planning_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("planning-engine")


def create_app(
    settings: Settings | None = None,
    *,
    repository: PlanningRepository | None = None,
    model_orchestration_port: ModelOrchestrationPort | None = None,
) -> FastAPI:
    """`model_orchestration_port`/`repository` are injectable (mirrors
    `digital-twin-engine`'s own `repository`/`communication_port` optional-
    injection pattern) so tests can pass fakes against a real `create_app()`
    and real (in-memory) event bus, instead of hand-rolling `app.state`."""
    settings = settings or Settings()
    configure_observability("planning-engine", log_level=settings.log_level)
    metrics = create_metrics()

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="planning-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    if model_orchestration_port is None:
        model_orchestration_port = ModelOrchestrationClient(
            bus, timeout_ms=settings.decomposition_model_orchestration_timeout_ms
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("planning-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_planning_engine.repository.postgres_planning_repository import (
                PostgresPlanningRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            repo = PostgresPlanningRepository(create_session_factory(engine))

        app.state.settings = settings
        app.state.metrics = metrics
        app.state.model_orchestration_port = model_orchestration_port
        app.state.repository = repo
        app.state.bus = bus

        await bus.connect()
        await bus.subscribe(
            "reasoning.process.completed", make_reasoning_process_completed_handler(app)
        )
        await bus.serve(
            "planning.decompose.request",
            make_decompose_request_handler(app),
            source_engine="planning-engine",
        )
        await bus.serve(
            "planning.goals.current.request",
            make_goals_current_request_handler(app),
            source_engine="planning-engine",
        )
        app.state.ready = True
        yield
        logger.info("planning-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="planning-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(plans_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

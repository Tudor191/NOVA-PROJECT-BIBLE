"""executive-cognition-engine's FastAPI entrypoint -- wires every port
(`GoalsPort`, `ExecutiveRepository`, the Event Bus) to their concrete
implementations, and registers `executive.arbitrate.request` and
`executive.outcome.report`, the two served RPCs declared in
`events/subscribed.py`. `workers/__init__.py` wires the same repository/bus
for the separate Arq worker process (docs/architecture/03-backend-
architecture.md §2's embedded-vs-standalone distinction, applied to
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

from nova_executive_cognition_engine.api.arbitrate import router as arbitrate_router
from nova_executive_cognition_engine.api.decisions import router as decisions_router
from nova_executive_cognition_engine.clients.goals_client import GoalsClient
from nova_executive_cognition_engine.config import Settings
from nova_executive_cognition_engine.domain.contender_registry import ContenderRegistry
from nova_executive_cognition_engine.domain.ports import ExecutiveRepository, GoalsPort
from nova_executive_cognition_engine.events.handlers import (
    make_arbitrate_request_handler,
    make_outcome_report_handler,
)
from nova_executive_cognition_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_executive_cognition_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_executive_cognition_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("executive-cognition-engine")


def create_app(
    settings: Settings | None = None,
    *,
    goals_port: GoalsPort | None = None,
    repository: ExecutiveRepository | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("executive-cognition-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = bind_event_bus(
        "executive-cognition-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("executive-cognition-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_executive_cognition_engine.repository.postgres_executive_repository import (
                PostgresExecutiveRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresExecutiveRepository(session_factory)

        goals = goals_port or GoalsClient(bus)

        await bus.connect()
        await bus.serve(
            "executive.arbitrate.request",
            make_arbitrate_request_handler(app),
            source_engine="executive-cognition-engine",
        )
        await bus.serve(
            "executive.outcome.report",
            make_outcome_report_handler(app),
            source_engine="executive-cognition-engine",
        )

        app.state.settings = settings
        app.state.goals_port = goals
        app.state.repository = repo
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.contender_registry = ContenderRegistry(
            ttl_seconds=settings.executive_engine_contender_registry_ttl_seconds,
            max_entries=settings.executive_engine_contender_registry_max_entries,
        )
        app.state.ready = True
        yield
        logger.info("executive-cognition-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(
        title="executive-cognition-engine", version="0.1.0", lifespan=lifespan
    )
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(arbitrate_router)
    fastapi_app.include_router(decisions_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

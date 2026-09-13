"""nova_autonomy_engine's FastAPI entrypoint.

`create_app` accepts the repository and the trust source as optional overrides
so tests can inject fakes without needing real Postgres reachable -- mirroring
`action-engine`'s and `capability-engine`'s own `main.py` precedent exactly.

**The `BoundEventBus` is constructed with two empty allow-lists and is never
used.** That is decision **D-4D-1**: 4D claims no `autonomy.*` subject, so this
engine publishes nothing and subscribes to nothing, and there is consequently
no autonomy subject that *could* leak to a browser (TDD §10 item 3). The bus is
still bound rather than omitted so the guarantee is a **runtime** one -- any
future `publish()` or `subscribe()` raises `SubjectNotAllowedError` rather than
succeeding against an unbound client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import create_engine, create_session_factory

from nova_autonomy_engine.api.autonomy import router as autonomy_router
from nova_autonomy_engine.api.health import router as health_router
from nova_autonomy_engine.clients.conversational_trust import (
    UnavailableConversationalTrustSource,
)
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.domain.ports import AutonomyRepository, ConversationalTrustSource
from nova_autonomy_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_autonomy_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_autonomy_engine.repository.postgres_autonomy_repository import (
    PostgresAutonomyRepository,
)

logger = get_logger("autonomy-engine")


def create_app(
    settings: Settings | None = None,
    *,
    repository: AutonomyRepository | None = None,
    trust_source: ConversationalTrustSource | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("autonomy-engine", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="autonomy-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("autonomy-engine starting")
        await bus.connect()
        app.state.bus = bus
        app.state.settings = settings

        engine = None
        if repository is None:
            engine = create_engine(settings.postgres_dsn)
            app.state.repository = PostgresAutonomyRepository(create_session_factory(engine))
        else:
            app.state.repository = repository

        app.state.trust_source = trust_source or UnavailableConversationalTrustSource()
        app.state.ready = True
        yield

        logger.info("autonomy-engine shutting down")
        app.state.ready = False
        if engine is not None:
            await engine.dispose()
        await bus.close()

    fastapi_app = FastAPI(title="autonomy-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(autonomy_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

"""personality-engine's FastAPI entrypoint -- wires `PersonalityRepository`
and the Event Bus to their concrete implementations, loads Core Identity and
Personality Memory into `app.state` once at startup (design doc Sec8, Sec12:
both served RPCs must be sub-millisecond, in-memory, no external calls per
request), and registers `personality.validate_response.request` /
`personality.style.select.request`, the two served RPCs declared in
`events/subscribed.py`.

Design doc Sec8's one no-graceful-degradation failure mode is implemented
here: if Core Identity fails to load (missing seed row, unreachable
Postgres), `app.state.core_identity` stays `None` and `app.state.ready` stays
`False` -- `/internal/readiness` reports not-ready and every endpoint that
needs identity returns 503, but the process does not crash, mirroring every
other engine's own `main.py` degraded-startup convention.

`create_app` accepts `repository` as an optional override so tests can inject
a fake without needing real Postgres reachable -- real infra is only
constructed when it isn't supplied (mirrors every other engine's `main.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_personality_engine.api.health import router as health_router
from nova_personality_engine.api.identity import router as identity_router
from nova_personality_engine.api.memory import router as memory_router
from nova_personality_engine.api.style import router as style_router
from nova_personality_engine.api.validate import router as validate_router
from nova_personality_engine.config import Settings
from nova_personality_engine.domain.models import MemoryProfile
from nova_personality_engine.domain.ports import PersonalityRepository
from nova_personality_engine.events.handlers import (
    make_style_select_handler,
    make_validate_response_handler,
)
from nova_personality_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_personality_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_personality_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("personality-engine")


def create_app(
    settings: Settings | None = None,
    *,
    repository: PersonalityRepository | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("personality-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="personality-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("personality-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_personality_engine.repository.db import (
                create_engine,
                create_session_factory,
            )
            from nova_personality_engine.repository.postgres_personality_repository import (
                PostgresPersonalityRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresPersonalityRepository(session_factory)

        await bus.connect()
        await bus.serve(
            "personality.validate_response.request",
            make_validate_response_handler(app),
            source_engine="personality-engine",
        )
        await bus.serve(
            "personality.style.select.request",
            make_style_select_handler(app),
            source_engine="personality-engine",
        )

        app.state.settings = settings
        app.state.repository = repo
        app.state.bus = bus
        app.state.metrics = metrics

        try:
            core_identity = await repo.get_core_identity()
        except Exception:
            logger.exception("personality-engine failed to load Core Identity at startup")
            core_identity = None
        app.state.core_identity = core_identity
        app.state.memory_profile = (
            await repo.get_memory_profile() if core_identity is not None else MemoryProfile()
        )

        if core_identity is None:
            logger.error(
                "personality-engine has no Core Identity -- staying not-ready "
                "(design doc Sec8: no runtime fallback for who NOVA is)"
            )
        app.state.ready = core_identity is not None

        yield
        logger.info("personality-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="personality-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(identity_router)
    fastapi_app.include_router(validate_router)
    fastapi_app.include_router(style_router)
    fastapi_app.include_router(memory_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

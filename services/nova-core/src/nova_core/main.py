"""nova-core's FastAPI entrypoint. In `embedded` local-first mode this process *is*
`nova-host` (docs/architecture/03-backend-architecture.md §2); in `standalone`
enterprise mode it is one container among many, communicating only over the Event
Bus. Phase 0 only exercises the boot sequence itself against an empty registry --
Roadmap Phase 1 is what starts registering real engines here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_core.api.health import router as health_router
from nova_core.config import NovaCoreSettings
from nova_core.domain.boot import NovaHost
from nova_core.domain.heartbeat import HeartbeatPublisher
from nova_core.domain.registry import ModuleRegistry
from nova_core.events.published import PUBLISHABLE_SUBJECTS
from nova_core.events.subscribed import SUBSCRIBABLE_SUBJECTS

logger = get_logger("nova-core")


def create_app(settings: NovaCoreSettings | None = None) -> FastAPI:
    settings = settings or NovaCoreSettings()
    configure_observability("nova-core", log_level=settings.log_level)

    registry = ModuleRegistry()
    bus = BoundEventBus(
        get_event_bus(),
        engine_name="nova-core",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    host = NovaHost(event_bus=bus, registry=registry)
    heartbeat = HeartbeatPublisher(
        event_bus=bus, host=host, interval_s=settings.heartbeat_interval_s
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("nova-core booting")
        await host.boot()
        heartbeat.start()
        logger.info("nova-core ready", extra={"uptime_seconds": host.uptime_seconds})
        yield
        logger.info("nova-core shutting down")
        await heartbeat.stop()
        await host.shutdown()

    fastapi_app = FastAPI(title="nova-core", version="0.1.0", lifespan=lifespan)
    fastapi_app.state.host = host
    fastapi_app.state.registry = registry
    fastapi_app.state.heartbeat = heartbeat
    fastapi_app.include_router(health_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

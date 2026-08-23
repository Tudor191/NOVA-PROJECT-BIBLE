"""nova_agent_os_kernel's FastAPI entrypoint -- health/readiness/metrics only
(TDD 3E §4: `agent-os/kernel` is control-plane infrastructure, not a
`/v1/...` request/reply service). Beyond health, this milestone wires only
the `agent_instance` persistence layer and restart reconciliation (TDD 3E
§4/§12) at startup -- no `planning.task_graph.created` consumption or
dispatch-loop (Scheduler) behavior is implemented here.

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres reachable -- mirrors every other
engine's `main.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.ports import KernelRepository
from nova_agent_os_kernel.domain.reconciliation import reconcile_running_instances
from nova_agent_os_kernel.events.published import PUBLISHABLE_SUBJECTS
from nova_agent_os_kernel.events.subscribed import SUBSCRIBABLE_SUBJECTS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("kernel")


def create_app(
    settings: Settings | None = None,
    *,
    repository: KernelRepository | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("kernel", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="kernel",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("kernel starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_agent_os_kernel.repository.postgres_kernel_repository import (
                PostgresKernelRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresKernelRepository(session_factory)

        app.state.settings = settings
        app.state.repository = repo
        app.state.bus = bus

        await bus.connect()

        reconciled = await reconcile_running_instances(repo, bus)
        if reconciled:
            logger.info(
                "kernel restart reconciliation: reconciled %d orphaned agent_instance row(s)",
                len(reconciled),
            )

        app.state.ready = True
        yield
        logger.info("kernel shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="kernel", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

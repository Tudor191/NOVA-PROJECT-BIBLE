"""nova_agent_os_kernel's FastAPI entrypoint -- health/readiness/metrics only
(TDD 3E §4: `agent-os/kernel` is control-plane infrastructure, not a
`/v1/...` request/reply service). Wires the `agent_instance` persistence
layer, restart reconciliation (TDD 3E §4/§12), and -- disclosed addition,
see `domain/scheduler.py`'s own module docstring -- the Kernel Scheduler's
own `planning.task_graph.created` subscription and its three upstream
ports (`RegistryPort`/`SupervisorPort`/`ModelGatewayPort`, via
`InprocessExecutionBackend`).

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres/event-bus reachable -- mirrors every
other engine's `main.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_agent_os_kernel.clients.model_gateway_client import ModelGatewayClient
from nova_agent_os_kernel.clients.registry_client import RegistryClient
from nova_agent_os_kernel.clients.supervisor_client import SupervisorClient
from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.execution_backend import InprocessExecutionBackend
from nova_agent_os_kernel.domain.ports import (
    AgentExecutionBackend,
    KernelRepository,
    RegistryPort,
    SupervisorPort,
)
from nova_agent_os_kernel.domain.reconciliation import reconcile_running_instances
from nova_agent_os_kernel.events.published import PUBLISHABLE_SUBJECTS
from nova_agent_os_kernel.events.scheduler_handler import make_task_graph_created_handler
from nova_agent_os_kernel.events.subscribed import SUBSCRIBABLE_SUBJECTS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("kernel")


def create_app(
    settings: Settings | None = None,
    *,
    repository: KernelRepository | None = None,
    registry_port: RegistryPort | None = None,
    supervisor_port: SupervisorPort | None = None,
    execution_backend: AgentExecutionBackend | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("kernel", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="kernel",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    if registry_port is None:
        registry_port = RegistryClient(bus)
    if supervisor_port is None:
        supervisor_port = SupervisorClient(bus)
    if execution_backend is None:
        execution_backend = InprocessExecutionBackend(
            agents_root=Path(settings.agents_root), model_gateway=ModelGatewayClient(bus)
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
        app.state.registry_port = registry_port
        app.state.supervisor_port = supervisor_port
        app.state.execution_backend = execution_backend

        await bus.connect()

        reconciled = await reconcile_running_instances(repo, bus)
        if reconciled:
            logger.info(
                "kernel restart reconciliation: reconciled %d orphaned agent_instance row(s)",
                len(reconciled),
            )

        await bus.subscribe(
            "planning.task_graph.created", make_task_graph_created_handler(app)
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

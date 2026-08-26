"""nova_agent_os_supervisors's FastAPI entrypoint -- health/readiness/metrics only (TDD 3E
§4: `agent-os/supervisors` is control-plane infrastructure, not a `/v1/...`
request/reply service)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_agent_os_supervisors.clients.decision_memory_client import LoggingDecisionMemoryClient
from nova_agent_os_supervisors.config import Settings
from nova_agent_os_supervisors.domain.ports import DecisionMemoryPort
from nova_agent_os_supervisors.events.peer_review_record_handler import (
    make_peer_review_record_handler,
)
from nova_agent_os_supervisors.events.published import PUBLISHABLE_SUBJECTS
from nova_agent_os_supervisors.events.restart_plan_handler import make_restart_plan_handler
from nova_agent_os_supervisors.events.subscribed import SUBSCRIBABLE_SUBJECTS

logger = get_logger("supervisors")


def create_app(
    settings: Settings | None = None,
    *,
    decision_memory_port: DecisionMemoryPort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("supervisors", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="supervisors",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    if decision_memory_port is None:
        decision_memory_port = LoggingDecisionMemoryClient()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("supervisors starting")
        await bus.connect()
        app.state.bus = bus
        app.state.decision_memory_port = decision_memory_port
        await bus.serve(
            "agent_os.supervisor.restart_plan.request",
            make_restart_plan_handler(app),
            source_engine="supervisors",
        )
        await bus.serve(
            "agent_os.supervisor.peer_review.request",
            make_peer_review_record_handler(app),
            source_engine="supervisors",
        )
        app.state.ready = True
        yield
        logger.info("supervisors shutting down")
        app.state.ready = False
        await bus.close()

    fastapi_app = FastAPI(title="supervisors", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

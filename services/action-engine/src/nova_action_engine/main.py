"""nova_action_engine's FastAPI entrypoint -- constructs the Postgres
repository and the three RPC-based ports (`CapabilityClient`,
`CommunicationClient`, `IdentityClient`); serves `action.execute`, the
single request/reply RPC this engine serves (TDD 3D §5, no real caller
until Phase 3E's Kernel Scheduler).

`create_app` accepts each port/repository as an optional override so tests
can inject fakes without needing real Postgres/event-bus reachable --
mirrors `capability-engine`'s own `main.py` precedent exactly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_contracts import ActionExecuteRequestPayload, ActionResultPayload, EventEnvelope
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_action_engine.api.approvals import router as approvals_router
from nova_action_engine.api.health import router as health_router
from nova_action_engine.clients.capability_client import CapabilityClient
from nova_action_engine.clients.communication_client import CommunicationClient
from nova_action_engine.clients.identity_client import IdentityClient
from nova_action_engine.config import Settings
from nova_action_engine.domain.pipeline import ActionStage, execute_action
from nova_action_engine.domain.ports import (
    ActionRepository,
    CapabilityPort,
    CommunicationPort,
    IdentityPort,
)
from nova_action_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_action_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_action_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("action-engine")


def _make_execute_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> ActionResultPayload:
        state = app.state
        payload = ActionExecuteRequestPayload.model_validate(envelope.payload)
        result = await execute_action(
            payload,
            repository=state.repository,
            capability_port=state.capability_port,
            communication_port=state.communication_port,
            identity_port=state.identity_port,
            event_publisher=state.bus,
            approval_timeout_seconds=state.settings.approval_timeout_seconds,
            on_stage=state.on_stage,
        )
        # `action_execute_total` (TDD 3D §9's named metric) is one increment
        # per RPC call, labeled by action_type/outcome -- distinct from the
        # per-stage `on_stage` callback below, which drives the other 5
        # named metrics from individual Action Principle lifecycle stages.
        state.metrics.action_execute_total.add(
            1, {"action_type": payload.action_type, "outcome": result.status}
        )
        return result

    return handle


def create_app(
    settings: Settings | None = None,
    *,
    repository: ActionRepository | None = None,
    capability_port: CapabilityPort | None = None,
    communication_port: CommunicationPort | None = None,
    identity_port: IdentityPort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("action-engine", log_level=settings.log_level)
    metrics = create_metrics()

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="action-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    if capability_port is None:
        capability_port = CapabilityClient(bus, timeout_ms=settings.capability_rpc_timeout_ms)
    if communication_port is None:
        communication_port = CommunicationClient(
            bus, timeout_ms=settings.communication_rpc_timeout_ms
        )
    if identity_port is None:
        identity_port = IdentityClient(bus, timeout_ms=settings.world_model_rpc_timeout_ms)

    async def on_stage(stage: ActionStage, outcome: str, detail: str | None) -> None:
        # Drives the 5 per-stage named metrics (TDD 3D §9) -- distinct from
        # `action_execute_total`, incremented once per RPC call above, not
        # per stage transition.
        if stage is ActionStage.PREPARE_RESOURCES and outcome == "blocked":
            metrics.action_approval_requested_total.add(1, {"risk": detail or "unknown"})
        elif stage is ActionStage.PREPARE_RESOURCES and outcome == "timeout":
            metrics.action_approval_timeout_total.add(1, {"risk": detail or "unknown"})
            metrics.action_approval_decided_total.add(1, {"decision": "denied"})
        elif stage is ActionStage.PREPARE_RESOURCES and outcome in ("approved", "denied"):
            metrics.action_approval_decided_total.add(1, {"decision": outcome})
        elif stage is ActionStage.RECOVER_IF_NECESSARY and outcome in ("success", "failure"):
            metrics.action_rollback_invoked_total.add(1, {"kind": detail or "unknown"})
        elif stage is ActionStage.CHECK_PERMISSIONS and outcome == "denied":
            risk_label = (detail or "").rsplit("risk=", 1)[-1] or "unknown"
            metrics.action_identity_confidence_denied_total.add(1, {"risk": risk_label})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("action-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_action_engine.repository.postgres_action_repository import (
                PostgresActionRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresActionRepository(session_factory)

        app.state.settings = settings
        app.state.metrics = metrics
        app.state.repository = repo
        app.state.capability_port = capability_port
        app.state.communication_port = communication_port
        app.state.identity_port = identity_port
        app.state.on_stage = on_stage
        app.state.bus = bus

        await bus.connect()
        await bus.serve(
            "action.execute",
            _make_execute_request_handler(app),
            source_engine="action-engine",
        )

        app.state.ready = True
        yield
        logger.info("action-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="action-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(approvals_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

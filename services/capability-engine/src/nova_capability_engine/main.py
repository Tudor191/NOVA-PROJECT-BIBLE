"""nova_capability_engine's FastAPI entrypoint -- constructs the Postgres
repository, the four built-in adapters, and `CommunicationClient`; serves
`capability.resolve.request`/`capability.invoke.request` (Fork 3C-1/3D-1's
RPC design -- this engine's own process owns and executes every adapter,
`action-engine`'s future `CapabilityPort`/client is not built here);
bootstrap-installs the four built-in capabilities through the real 8-stage
pipeline at startup (TDD 3C §2.3, §0).

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres reachable -- mirrors every other
engine's `main.py` (`ai-model-orchestration-engine`'s own precedent)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_contracts import (
    CapabilityInvokeReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityResolveRequestPayload,
    EventEnvelope,
)
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_capability_engine.adapters.registry import build_adapter_registry
from nova_capability_engine.api.capabilities import router as capabilities_router
from nova_capability_engine.api.health import router as health_router
from nova_capability_engine.clients.communication_client import CommunicationClient
from nova_capability_engine.config import Settings
from nova_capability_engine.domain.builtin_capabilities import build_builtin_manifests
from nova_capability_engine.domain.pipeline import InstallationStage, install_capability
from nova_capability_engine.domain.ports import (
    AdapterPort,
    CapabilityRepository,
    CommunicationPort,
)
from nova_capability_engine.domain.sandbox import SandboxViolation
from nova_capability_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_capability_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_capability_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("capability-engine")


def _make_resolve_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> CapabilityResolveReplyPayload:
        state = app.state
        payload = CapabilityResolveRequestPayload.model_validate(envelope.payload)
        capability = await state.repository.find_by_id(payload.capability_id)
        return CapabilityResolveReplyPayload(found=capability is not None, capability=capability)

    return handle


def _make_invoke_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> CapabilityInvokeReplyPayload:
        state = app.state
        payload = CapabilityInvokeRequestPayload.model_validate(envelope.payload)
        capability = await state.repository.find_by_id(payload.capability_id)
        if capability is None:
            return CapabilityInvokeReplyPayload(outcome="failure", error="capability not found")
        adapter = state.adapters.get(capability.execution_adapter)
        if adapter is None:
            return CapabilityInvokeReplyPayload(
                outcome="failure",
                error=f"no adapter registered for {capability.execution_adapter!r}",
            )
        started = time.monotonic()
        try:
            try:
                result = await adapter.invoke(
                    payload.operation,
                    payload.parameters,
                    required_resources=capability.required_resources,
                )
            except SandboxViolation as exc:
                state.metrics.sandbox_violation_blocked_total.add(
                    1, {"adapter": capability.execution_adapter}
                )
                state.metrics.invocation_total.add(
                    1, {"adapter": capability.execution_adapter, "outcome": "sandbox_violation"}
                )
                return CapabilityInvokeReplyPayload(outcome="sandbox_violation", error=str(exc))
            except Exception as exc:  # noqa: BLE001 -- structured reply, never a crash (TDD 3C §8)
                state.metrics.invocation_total.add(
                    1, {"adapter": capability.execution_adapter, "outcome": "failure"}
                )
                return CapabilityInvokeReplyPayload(outcome="failure", error=str(exc))
        finally:
            duration_ms = (time.monotonic() - started) * 1000
            state.metrics.invocation_duration_ms.record(
                duration_ms, {"adapter": capability.execution_adapter}
            )
        state.metrics.invocation_total.add(
            1, {"adapter": capability.execution_adapter, "outcome": "success"}
        )
        return CapabilityInvokeReplyPayload(outcome="success", result=result)

    return handle


def create_app(
    settings: Settings | None = None,
    *,
    repository: CapabilityRepository | None = None,
    adapters: dict[str, AdapterPort] | None = None,
    communication_port: CommunicationPort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("capability-engine", log_level=settings.log_level)
    metrics = create_metrics()

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="capability-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    if communication_port is None:
        communication_port = CommunicationClient(
            bus, timeout_ms=settings.communication_rpc_timeout_ms
        )

    async def on_install_stage(stage: InstallationStage, outcome: str) -> None:
        metrics.install_pipeline_stage_total.add(1, {"stage": stage.value, "outcome": outcome})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("capability-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_capability_engine.repository.postgres_capability_repository import (
                PostgresCapabilityRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresCapabilityRepository(session_factory)

        adapter_registry = (
            adapters
            if adapters is not None
            else build_adapter_registry(
                terminal_timeout_s=settings.sandbox_terminal_timeout_s,
                http_timeout_s=settings.sandbox_http_timeout_s,
            )
        )

        app.state.settings = settings
        app.state.metrics = metrics
        app.state.repository = repo
        app.state.adapters = adapter_registry
        app.state.communication_port = communication_port
        app.state.on_install_stage = on_install_stage
        app.state.bus = bus

        await bus.connect()
        await bus.serve(
            "capability.resolve.request",
            _make_resolve_request_handler(app),
            source_engine="capability-engine",
        )
        await bus.serve(
            "capability.invoke.request",
            _make_invoke_request_handler(app),
            source_engine="capability-engine",
        )

        for manifest in build_builtin_manifests(
            filesystem_root=settings.sandbox_filesystem_root,
            terminal_allowed_executables=settings.sandbox_terminal_allowed_executables,
            http_allowed_hosts=settings.sandbox_http_allowed_hosts,
        ):
            await install_capability(
                manifest,
                repository=repo,
                adapters=adapter_registry,
                communication_port=communication_port,
                primary_user_id=settings.primary_user_id,
                on_stage=on_install_stage,
            )

        app.state.ready = True
        yield
        logger.info("capability-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="capability-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(capabilities_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

"""ai-model-orchestration-engine's FastAPI entrypoint -- wires every port
(`ModelRegistryRepository`, `UsageRepository`, `ConnectorFactory`, the Event
Bus) to their concrete implementations, and registers the served RPCs
declared in `events/subscribed.py`. `workers/__init__.py` wires the same ports
for the separate Arq worker process (docs/architecture/03-backend-architecture.md
§2's embedded-vs-standalone distinction, applied to workers).

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres/Ollama/Anthropic reachable -- real infra is
only constructed for whichever port isn't supplied (mirrors every other
engine's `main.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import FastAPI
from nova_contracts import (
    EmbedReplyPayload,
    EmbedRequestPayload,
    EventEnvelope,
    GenerateReplyPayload,
    GenerateRequestPayload,
    ToolCallPayload,
)
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_ai_model_orchestration_engine.api.embed import router as embed_router
from nova_ai_model_orchestration_engine.api.generate import router as generate_router
from nova_ai_model_orchestration_engine.api.health import router as health_router
from nova_ai_model_orchestration_engine.api.models import router as models_router
from nova_ai_model_orchestration_engine.api.usage import router as usage_router
from nova_ai_model_orchestration_engine.config import Settings
from nova_ai_model_orchestration_engine.connectors.factory import ConnectorFactory
from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    ContextComponent,
    GenerateRequest,
    ToolSchema,
)
from nova_ai_model_orchestration_engine.domain.ports import (
    ModelRegistryRepository,
    UsageRepository,
)
from nova_ai_model_orchestration_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_ai_model_orchestration_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_ai_model_orchestration_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("ai-model-orchestration-engine")


def _make_generate_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> GenerateReplyPayload:
        state = app.state
        payload = GenerateRequestPayload.model_validate(envelope.payload)
        domain_request = GenerateRequest(
            context=[
                ContextComponent(
                    source=c.source,
                    text=c.text,
                    token_estimate=c.token_estimate,
                    priority=c.priority,
                    truncation_policy=c.truncation_policy,
                )
                for c in payload.context
            ],
            tools=[
                ToolSchema(
                    name=t.name,
                    description=t.description,
                    parameters_json_schema=t.parameters_json_schema,
                )
                for t in payload.tools
            ],
            task_type=payload.task_type,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
            preferred_model_id=payload.preferred_model_id,
            max_output_tokens=payload.max_output_tokens,
        )
        models = await state.registry_repository.list_all()
        try:
            outcome = await routing.execute_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return GenerateReplyPayload(
                text="",
                input_tokens=0,
                output_tokens=0,
                finish_reason="error",
                structural_confidence=0.0,
                model_id=UUID(int=0),
                provider="unknown",
                error=str(exc),
            )
        model = next(m for m in models if m.id == outcome.decision.selected_model_id)
        state.metrics.requests_total.add(
            1, {"outcome": "fallback" if outcome.fallback_used else "success"}
        )
        result = outcome.result
        return GenerateReplyPayload(
            text=result.text,
            tool_calls=[
                ToolCallPayload(id=tc.id, tool_name=tc.tool_name, arguments=tc.arguments)
                for tc in result.tool_calls
            ],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            finish_reason=result.finish_reason,
            structural_confidence=result.structural_confidence,
            model_id=model.id,
            provider=model.provider,
        )

    return handle


def _make_embed_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> EmbedReplyPayload:
        state = app.state
        payload = EmbedRequestPayload.model_validate(envelope.payload)
        models = await state.registry_repository.list_all()
        try:
            model, embeddings = await routing.embed_and_record(
                payload.texts,
                models,
                privacy_hint=payload.privacy_hint,
                requesting_engine=payload.requesting_engine,
                correlation_id=payload.correlation_id,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return EmbedReplyPayload(
                embeddings=[], model_id=payload.correlation_id, provider="unknown", error=str(exc)
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return EmbedReplyPayload(embeddings=embeddings, model_id=model.id, provider=model.provider)

    return handle


def create_app(
    settings: Settings | None = None,
    *,
    registry_repository: ModelRegistryRepository | None = None,
    usage_repository: UsageRepository | None = None,
    connector_factory: ConnectorFactory | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("ai-model-orchestration-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="ai-model-orchestration-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("ai-model-orchestration-engine starting")

        engine: AsyncEngine | None = None
        registry_repo = registry_repository
        usage_repo = usage_repository
        if registry_repo is None or usage_repo is None:
            from nova_ai_model_orchestration_engine.repository.db import (
                create_engine,
                create_session_factory,
            )
            from nova_ai_model_orchestration_engine.repository.postgres_registry_repository import (
                PostgresModelRegistryRepository,
            )
            from nova_ai_model_orchestration_engine.repository.postgres_usage_repository import (
                PostgresUsageRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            registry_repo = registry_repo or PostgresModelRegistryRepository(session_factory)
            usage_repo = usage_repo or PostgresUsageRepository(session_factory)

        factory = connector_factory or ConnectorFactory(
            ollama_base_url=settings.ollama_base_url,
            anthropic_api_key=settings.anthropic_api_key or None,
            timeout_s=settings.connector_timeout_s,
        )

        await bus.connect()
        await bus.serve(
            "ai_model.generate.request",
            _make_generate_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )
        await bus.serve(
            "ai_model.embed.request",
            _make_embed_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )

        app.state.settings = settings
        app.state.registry_repository = registry_repo
        app.state.usage_repository = usage_repo
        app.state.connector_factory = factory
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.ready = True
        yield
        logger.info("ai-model-orchestration-engine shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(
        title="ai-model-orchestration-engine", version="0.1.0", lifespan=lifespan
    )
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(models_router)
    fastapi_app.include_router(generate_router)
    fastapi_app.include_router(embed_router)
    fastapi_app.include_router(usage_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

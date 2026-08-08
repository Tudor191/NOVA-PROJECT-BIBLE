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
    FaceEmbedReplyPayload,
    FaceEmbedRequestPayload,
    GazeEstimateReplyPayload,
    GazeEstimateRequestPayload,
    GenerateReplyPayload,
    GenerateRequestPayload,
    SynthesizeReplyPayload,
    SynthesizeRequestPayload,
    ToolCallPayload,
    TranscribeReplyPayload,
    TranscribeRequestPayload,
    VoiceEmbedReplyPayload,
    VoiceEmbedRequestPayload,
    WakePhraseDetectReplyPayload,
    WakePhraseDetectRequestPayload,
)
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_ai_model_orchestration_engine.api.embed import router as embed_router
from nova_ai_model_orchestration_engine.api.face_embed import router as face_embed_router
from nova_ai_model_orchestration_engine.api.gaze_estimate import router as gaze_estimate_router
from nova_ai_model_orchestration_engine.api.generate import router as generate_router
from nova_ai_model_orchestration_engine.api.models import router as models_router
from nova_ai_model_orchestration_engine.api.synthesize import router as synthesize_router
from nova_ai_model_orchestration_engine.api.transcribe import router as transcribe_router
from nova_ai_model_orchestration_engine.api.usage import router as usage_router
from nova_ai_model_orchestration_engine.api.voice_embed import router as voice_embed_router
from nova_ai_model_orchestration_engine.api.wake_phrase import router as wake_phrase_router
from nova_ai_model_orchestration_engine.config import Settings
from nova_ai_model_orchestration_engine.connectors.factory import ConnectorFactory
from nova_ai_model_orchestration_engine.domain import router as routing
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    ContextComponent,
    FaceEmbedRequest,
    GazeEstimateRequest,
    GenerateRequest,
    SynthesizeRequest,
    ToolSchema,
    TranscribeRequest,
    VoiceEmbedRequest,
    WakePhraseRequest,
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


def _make_transcribe_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> TranscribeReplyPayload:
        state = app.state
        payload = TranscribeRequestPayload.model_validate(envelope.payload)
        domain_request = TranscribeRequest(
            audio_bytes=payload.audio_bytes,
            audio_format=payload.audio_format,
            language_hint=payload.language_hint,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
        )
        models = await state.registry_repository.list_all()
        try:
            model, result = await routing.transcribe_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return TranscribeReplyPayload(
                text="",
                structural_confidence=0.0,
                model_id=UUID(int=0),
                provider="unknown",
                error=str(exc),
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return TranscribeReplyPayload(
            text=result.text,
            detected_language=result.detected_language,
            structural_confidence=result.structural_confidence,
            model_id=model.id,
            provider=model.provider,
        )

    return handle


def _make_synthesize_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> SynthesizeReplyPayload:
        state = app.state
        payload = SynthesizeRequestPayload.model_validate(envelope.payload)
        domain_request = SynthesizeRequest(
            text=payload.text,
            voice_profile=payload.voice_profile,
            audio_format=payload.audio_format,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
        )
        models = await state.registry_repository.list_all()
        try:
            model, result = await routing.synthesize_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return SynthesizeReplyPayload(
                audio_bytes=b"",
                audio_format=payload.audio_format,
                structural_confidence=0.0,
                model_id=UUID(int=0),
                provider="unknown",
                error=str(exc),
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return SynthesizeReplyPayload(
            audio_bytes=result.audio_bytes,
            audio_format=result.audio_format,
            structural_confidence=result.structural_confidence,
            model_id=model.id,
            provider=model.provider,
        )

    return handle


def _make_detect_wake_phrase_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> WakePhraseDetectReplyPayload:
        state = app.state
        payload = WakePhraseDetectRequestPayload.model_validate(envelope.payload)
        domain_request = WakePhraseRequest(
            audio_bytes=payload.audio_bytes,
            audio_format=payload.audio_format,
            wake_phrase=payload.wake_phrase,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
        )
        models = await state.registry_repository.list_all()
        try:
            model, result = await routing.detect_wake_phrase_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return WakePhraseDetectReplyPayload(
                matched=False,
                structural_confidence=0.0,
                model_id=UUID(int=0),
                provider="unknown",
                error=str(exc),
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return WakePhraseDetectReplyPayload(
            matched=result.matched,
            structural_confidence=result.structural_confidence,
            model_id=model.id,
            provider=model.provider,
        )

    return handle


def _make_embed_voice_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> VoiceEmbedReplyPayload:
        state = app.state
        payload = VoiceEmbedRequestPayload.model_validate(envelope.payload)
        domain_request = VoiceEmbedRequest(
            audio_bytes=payload.audio_bytes,
            audio_format=payload.audio_format,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
        )
        models = await state.registry_repository.list_all()
        try:
            model, result = await routing.embed_voice_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return VoiceEmbedReplyPayload(
                embedding=[], model_id=UUID(int=0), provider="unknown", error=str(exc)
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return VoiceEmbedReplyPayload(
            embedding=result.embedding, model_id=model.id, provider=model.provider
        )

    return handle


def _make_embed_face_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> FaceEmbedReplyPayload:
        state = app.state
        payload = FaceEmbedRequestPayload.model_validate(envelope.payload)
        domain_request = FaceEmbedRequest(
            image_bytes=payload.image_bytes,
            image_format=payload.image_format,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
        )
        models = await state.registry_repository.list_all()
        try:
            model, result = await routing.embed_face_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return FaceEmbedReplyPayload(
                embedding=[], model_id=UUID(int=0), provider="unknown", error=str(exc)
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return FaceEmbedReplyPayload(
            embedding=result.embedding, model_id=model.id, provider=model.provider
        )

    return handle


def _make_estimate_gaze_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> GazeEstimateReplyPayload:
        state = app.state
        payload = GazeEstimateRequestPayload.model_validate(envelope.payload)
        domain_request = GazeEstimateRequest(
            image_bytes=payload.image_bytes,
            image_format=payload.image_format,
            privacy_hint=payload.privacy_hint,
            requesting_engine=payload.requesting_engine,
            correlation_id=payload.correlation_id,
        )
        models = await state.registry_repository.list_all()
        try:
            model, result = await routing.estimate_gaze_and_record(
                domain_request,
                models,
                get_connector=state.connector_factory.get_connector,
                usage_repository=state.usage_repository,
            )
        except FallbackExhaustedError as exc:
            state.metrics.requests_total.add(1, {"outcome": "failed"})
            return GazeEstimateReplyPayload(
                gaze_direction="unknown",
                structural_confidence=0.0,
                model_id=UUID(int=0),
                provider="unknown",
                error=str(exc),
            )
        state.metrics.requests_total.add(1, {"outcome": "success"})
        return GazeEstimateReplyPayload(
            gaze_direction=result.gaze_direction,
            structural_confidence=result.structural_confidence,
            model_id=model.id,
            provider=model.provider,
        )

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

    bus = bind_event_bus(
        "ai-model-orchestration-engine",
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
            from nova_service_kit import create_engine, create_session_factory

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
            whisper_base_url=settings.whisper_base_url,
            piper_base_url=settings.piper_base_url,
            wake_word_base_url=settings.wake_word_base_url,
            voice_embedding_base_url=settings.voice_embedding_base_url,
            face_embedding_base_url=settings.face_embedding_base_url,
            gaze_estimation_base_url=settings.gaze_estimation_base_url,
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
        await bus.serve(
            "ai_model.transcribe.request",
            _make_transcribe_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )
        await bus.serve(
            "ai_model.synthesize.request",
            _make_synthesize_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )
        await bus.serve(
            "ai_model.detect_wake_phrase.request",
            _make_detect_wake_phrase_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )
        await bus.serve(
            "ai_model.embed_voice.request",
            _make_embed_voice_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )
        await bus.serve(
            "ai_model.embed_face.request",
            _make_embed_face_request_handler(app),
            source_engine="ai-model-orchestration-engine",
        )
        await bus.serve(
            "ai_model.estimate_gaze.request",
            _make_estimate_gaze_request_handler(app),
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
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(models_router)
    fastapi_app.include_router(generate_router)
    fastapi_app.include_router(embed_router)
    fastapi_app.include_router(transcribe_router)
    fastapi_app.include_router(synthesize_router)
    fastapi_app.include_router(wake_phrase_router)
    fastapi_app.include_router(voice_embed_router)
    fastapi_app.include_router(face_embed_router)
    fastapi_app.include_router(gaze_estimate_router)
    fastapi_app.include_router(usage_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

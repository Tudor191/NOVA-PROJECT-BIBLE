"""memory-engine's FastAPI entrypoint -- wires every port (`MemoryRepository`,
`VectorIndex`, `EmbeddingProvider`, the Event Bus) to their concrete implementations,
and registers the request/reply server and event subscriptions declared in
`events/subscribed.py`. `workers/__init__.py` wires the same ports for the separate
Arq worker process (docs/architecture/03-backend-architecture.md §2's embedded-vs-
standalone distinction, applied to workers).

`create_app` accepts each port as an optional override so tests can inject fakes
(`nova-testkit`-style in-memory doubles) without needing a real Postgres/Redis/Ollama
reachable -- real infra is only constructed for whichever port isn't supplied. This
is what makes `tests/integration/` runnable without Docker (docs/architecture/16 §3
still requires the real-backend suite too; see that directory's `test_*_real.py`
files, skipped unless real infra is configured).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_contracts import (
    EventEnvelope,
    MemoryRetrieveReplyPayload,
    MemoryRetrieveRequestPayload,
    MemorySearchResultPayload,
)
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_memory_engine.api.decisions import router as decisions_router
from nova_memory_engine.api.memories import router as memories_router
from nova_memory_engine.config import Settings
from nova_memory_engine.domain import retrieval
from nova_memory_engine.domain.ports import EmbeddingProvider, MemoryRepository, VectorIndex
from nova_memory_engine.events import handlers
from nova_memory_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_memory_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_memory_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("memory-engine")

VECTOR_COLLECTION = "memory_records"
VECTOR_METADATA_COLUMNS = (
    "embedding_model",
    "user_id",
    "memory_type",
    "content",
    "confidence",
    "importance_score",
    "knowledge_node_id",
)


def _make_retrieve_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> MemoryRetrieveReplyPayload:
        state = app.state
        request_payload = MemoryRetrieveRequestPayload.model_validate(envelope.payload)
        start = time.perf_counter()
        result = await retrieval.retrieve(
            retrieval.RetrievalQuery(
                user_id=request_payload.user_id,
                correlation_id=envelope.correlation_id,
                query_text=request_payload.query_text,
                project_id=request_payload.project_id,
                memory_type=request_payload.memory_type,
                include_relationships=request_payload.include_relationships,
                limit=request_payload.limit,
            ),
            repository=state.memory_repository,
            vector_index=state.vector_index,
            embedding_provider=state.embedding_provider,
            event_publisher=state.bus,
        )
        state.metrics.retrieval_duration_seconds.record(time.perf_counter() - start)
        if result.degraded:
            state.metrics.retrieval_degraded_total.add(1)
        return MemoryRetrieveReplyPayload(
            results=[
                MemorySearchResultPayload.model_validate(r, from_attributes=True)
                for r in result.results
            ],
            degraded=result.degraded,
        )

    return handle


def create_app(
    settings: Settings | None = None,
    *,
    memory_repository: MemoryRepository | None = None,
    vector_index: VectorIndex | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("memory-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = bind_event_bus(
        "memory-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("memory-engine starting")

        engine: AsyncEngine | None = None
        repo = memory_repository
        if repo is None:
            # Lazy imports: SQLAlchemy/asyncpg should not be required just to
            # import this module when a fake repository is injected (tests).
            from nova_service_kit import create_engine, create_session_factory

            from nova_memory_engine.repository.postgres_memory_repository import (
                PostgresMemoryRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            repo = PostgresMemoryRepository(create_session_factory(engine))

        vidx = vector_index
        if vidx is None:
            from nova_vectorstore_sdk.backends.pgvector import PgVectorCollection, PgVectorStore

            vidx = PgVectorStore(
                dsn=settings.vector_store_dsn(),
                collections={
                    VECTOR_COLLECTION: PgVectorCollection(
                        table="memory.memory_record", metadata_columns=VECTOR_METADATA_COLUMNS
                    )
                },
            )
        await vidx.connect()

        eprov = embedding_provider
        if eprov is None:
            from nova_embeddings_sdk.factory import get_embedding_provider

            eprov = get_embedding_provider()

        await bus.connect()
        await bus.serve(
            "memory.retrieve.request", _make_retrieve_handler(app), source_engine="memory-engine"
        )
        await bus.subscribe(
            "perception.*.observed", handlers.make_perception_observed_handler(repo)
        )
        await bus.subscribe("action.result", handlers.make_action_result_handler(repo))
        await bus.subscribe(
            "communication.intent.received", handlers.make_communication_intent_handler(repo)
        )
        await bus.subscribe(
            "agent_os.task.completed", handlers.make_agent_os_task_completed_handler(repo)
        )
        await bus.subscribe(
            "knowledge.contradiction.detected", handlers.make_knowledge_contradiction_handler(repo)
        )

        app.state.settings = settings
        app.state.memory_repository = repo
        app.state.vector_index = vidx
        app.state.embedding_provider = eprov
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.ready = True
        yield
        logger.info("memory-engine shutting down")
        app.state.ready = False
        await bus.close()
        await vidx.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="memory-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(memories_router)
    fastapi_app.include_router(decisions_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

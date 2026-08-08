"""knowledge-engine's FastAPI entrypoint -- wires every port
(`KnowledgeMetadataRepository`, `VectorIndex`, `EmbeddingProvider`, `GraphStore`,
the Event Bus) to their concrete implementations, and registers the request/reply
servers and event subscriptions declared in `events/subscribed.py`.
`workers/__init__.py` wires the same ports for the separate Arq worker process
(docs/architecture/03-backend-architecture.md §2's embedded-vs-standalone
distinction, applied to workers).

`create_app` accepts each port as an optional override so tests can inject fakes
without needing real Postgres/Neo4j/Ollama reachable -- real infra is only
constructed for whichever port isn't supplied (mirrors Memory Engine's
`main.py`).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_contracts import (
    EventEnvelope,
    KnowledgeLinkReplyPayload,
    KnowledgeLinkRequestPayload,
    KnowledgeRetrieveReplyPayload,
    KnowledgeRetrieveRequestPayload,
    KnowledgeSearchResultPayload,
    KnowledgeTraverseReplyPayload,
    KnowledgeTraverseRequestPayload,
)
from nova_eventbus_sdk import bind_event_bus
from nova_graphstore_sdk import TraversalDirection, TraversalSpec
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_knowledge_engine.api.contradictions import router as contradictions_router
from nova_knowledge_engine.api.graph import router as graph_router
from nova_knowledge_engine.api.nodes import router as nodes_router
from nova_knowledge_engine.config import Settings
from nova_knowledge_engine.domain import acquisition, graph_operations, normalization, retrieval
from nova_knowledge_engine.domain.normalization import RawInformation
from nova_knowledge_engine.domain.ports import (
    EmbeddingProvider,
    GraphStore,
    KnowledgeMetadataRepository,
    VectorIndex,
)
from nova_knowledge_engine.events import handlers
from nova_knowledge_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_knowledge_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_knowledge_engine.observability import create_metrics

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("knowledge-engine")

VECTOR_COLLECTION = "knowledge_nodes"
VECTOR_METADATA_COLUMNS = ("embedding_model", "scope", "project_id", "user_id", "label")


def _make_retrieve_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> KnowledgeRetrieveReplyPayload:
        state = app.state
        payload = KnowledgeRetrieveRequestPayload.model_validate(envelope.payload)
        start = time.perf_counter()
        result = await retrieval.retrieve(
            retrieval.RetrievalQuery(
                correlation_id=envelope.correlation_id,
                query_text=payload.query_text,
                seed_node_id=payload.seed_node_id,
                scope=payload.scope,
                project_id=payload.project_id,
                user_id=payload.user_id,
                max_hops=payload.max_hops,
                limit=payload.limit,
            ),
            repository=state.repository,
            vector_index=state.vector_index,
            embedding_provider=state.embedding_provider,
            graph_store=state.graph_store,
        )
        state.metrics.retrieval_duration_seconds.record(time.perf_counter() - start)
        if result.degraded:
            state.metrics.retrieval_degraded_total.add(1)
        return KnowledgeRetrieveReplyPayload(
            results=[
                KnowledgeSearchResultPayload(
                    node_id=r.node_id,
                    label=r.label,
                    name=r.name,
                    score=r.score,
                    similarity=r.similarity,
                    confidence=r.confidence,
                    layer=r.layer,
                    related_node_ids=list(r.related_node_ids),
                )
                for r in result.results
            ],
            degraded=result.degraded,
        )

    return handle


def _make_traverse_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> KnowledgeTraverseReplyPayload:
        state = app.state
        payload = KnowledgeTraverseRequestPayload.model_validate(envelope.payload)
        try:
            result = await state.graph_store.traverse(
                payload.seed_node_id,
                TraversalSpec(direction=TraversalDirection.BOTH, max_hops=payload.max_hops),
            )
        except Exception:
            logger.warning("knowledge.traverse.request degraded", exc_info=True)
            return KnowledgeTraverseReplyPayload(connected_node_ids=[])
        connected = [n.id for n in result.nodes if n.id != payload.seed_node_id]
        return KnowledgeTraverseReplyPayload(connected_node_ids=connected)

    return handle


def _make_link_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> KnowledgeLinkReplyPayload:
        """Create-or-find a `:Concept` node for `concept_name` and link it to the
        memory that requested it (docs/design/phase-1/02-knowledge-engine.md §13,
        served for Memory Engine's `domain/relationship.py`). Returns the
        deterministic node id regardless of acquisition outcome (created,
        corroborated, or conflict) -- `normalization.node_id_for` is stable, so a
        caller can store the link even if the underlying node write is still
        pending the async saga (§17) or is momentarily blocked on an open
        contradiction."""
        state = app.state
        payload = KnowledgeLinkRequestPayload.model_validate(envelope.payload)
        raw = RawInformation(
            label="Concept",
            name=payload.concept_name,
            source_type="memory_link",
            source_ref=str(payload.memory_id),
        )
        candidate_node_id = normalization.node_id_for(
            label=raw.label,
            name=raw.name,
            scope=raw.scope,
            project_id=raw.project_id,
            user_id=raw.user_id,
        )
        result = await acquisition.ingest(
            state.repository, raw, correlation_id=envelope.correlation_id
        )
        if result.outcome == "conflict":
            state.metrics.contradictions_detected_total.add(1)
        if result.node is not None:
            await graph_operations.link_memory_reference(
                state.repository,
                concept_node_id=result.node.node_id,
                memory_id=payload.memory_id,
                confidence=result.node.confidence,
                source="memory-engine",
                correlation_id=envelope.correlation_id,
            )
        return KnowledgeLinkReplyPayload(knowledge_node_id=candidate_node_id)

    return handle


def create_app(
    settings: Settings | None = None,
    *,
    repository: KnowledgeMetadataRepository | None = None,
    vector_index: VectorIndex | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    graph_store: GraphStore | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("knowledge-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = bind_event_bus(
        "knowledge-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("knowledge-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_knowledge_engine.repository.postgres_metadata_repository import (
                PostgresMetadataRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            repo = PostgresMetadataRepository(create_session_factory(engine))

        vidx = vector_index
        if vidx is None:
            from nova_vectorstore_sdk.backends.pgvector import PgVectorCollection, PgVectorStore

            vidx = PgVectorStore(
                dsn=settings.vector_store_dsn(),
                collections={
                    VECTOR_COLLECTION: PgVectorCollection(
                        table="knowledge.node_metadata",
                        id_column="node_id",
                        metadata_columns=VECTOR_METADATA_COLUMNS,
                    )
                },
            )
        await vidx.connect()

        eprov = embedding_provider
        if eprov is None:
            from nova_embeddings_sdk.factory import get_embedding_provider

            eprov = get_embedding_provider()

        gstore = graph_store
        if gstore is None:
            from nova_graphstore_sdk.factory import get_graph_store

            gstore = get_graph_store()
        await gstore.connect()

        await bus.connect()
        await bus.serve(
            "knowledge.retrieve.request",
            _make_retrieve_handler(app),
            source_engine="knowledge-engine",
        )
        await bus.serve(
            "knowledge.traverse.request",
            _make_traverse_handler(app),
            source_engine="knowledge-engine",
        )
        await bus.serve(
            "knowledge.link.request", _make_link_handler(app), source_engine="knowledge-engine"
        )
        await bus.subscribe(
            "memory.long_term.created", handlers.make_memory_long_term_created_handler(repo)
        )
        await bus.subscribe(
            "perception.filesystem.observed",
            handlers.make_perception_filesystem_observed_handler(repo),
        )

        app.state.settings = settings
        app.state.repository = repo
        app.state.vector_index = vidx
        app.state.embedding_provider = eprov
        app.state.graph_store = gstore
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.ready = True
        yield
        logger.info("knowledge-engine shutting down")
        app.state.ready = False
        await bus.close()
        await vidx.close()
        await gstore.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="knowledge-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(nodes_router)
    fastapi_app.include_router(graph_router)
    fastapi_app.include_router(contradictions_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

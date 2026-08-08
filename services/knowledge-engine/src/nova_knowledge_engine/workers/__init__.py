"""Arq `WorkerSettings` -- run via `arq nova_knowledge_engine.workers.WorkerSettings`.

Wires the same ports (`KnowledgeMetadataRepository`, `VectorIndex`,
`EmbeddingProvider`, `GraphStore`, `EventBus`) as `main.py`'s FastAPI app; workers
and the API are two deployments of the same domain logic, matching the
embedded-vs-standalone distinction (docs/architecture/03-backend-architecture.md
§2) applied at the process level -- `standalone` mode runs this as its own `arq`
process, and nothing here prevents a future `embedded` mode from driving the same
cron schedule in-process instead.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger
from nova_service_kit import create_engine, create_session_factory

from nova_knowledge_engine.config import Settings
from nova_knowledge_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_knowledge_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_knowledge_engine.observability import create_metrics
from nova_knowledge_engine.repository.postgres_metadata_repository import (
    PostgresMetadataRepository,
)
from nova_knowledge_engine.workers.embedding_worker import arq_run_embedding_pass
from nova_knowledge_engine.workers.maintenance_worker import arq_run_maintenance
from nova_knowledge_engine.workers.outbox_worker import arq_run_outbox_dispatch

_SETTINGS = Settings()
logger = get_logger("knowledge-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    from nova_embeddings_sdk.factory import get_embedding_provider
    from nova_graphstore_sdk.factory import get_graph_store
    from nova_vectorstore_sdk.backends.pgvector import PgVectorCollection, PgVectorStore

    # A separate OS process from the FastAPI app (docs/architecture/03 §2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("knowledge-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("knowledge-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    vector_index = PgVectorStore(
        dsn=_SETTINGS.vector_store_dsn(),
        collections={
            "knowledge_nodes": PgVectorCollection(
                table="knowledge.node_metadata",
                id_column="node_id",
                metadata_columns=("embedding_model", "scope", "project_id", "user_id", "label"),
            )
        },
    )
    await vector_index.connect()

    graph_store = get_graph_store()
    await graph_store.connect()

    bus = bind_event_bus(
        "knowledge-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["repository"] = PostgresMetadataRepository(session_factory)
    ctx["vector_index"] = vector_index
    ctx["embedding_provider"] = get_embedding_provider()
    ctx["embedding_model"] = _SETTINGS.embedding_model
    ctx["graph_store"] = graph_store
    ctx["bus"] = bus
    ctx["graph_write_degraded_threshold_minutes"] = (
        _SETTINGS.graph_write_degraded_threshold_minutes
    )
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("knowledge-engine worker shutting down")
    await ctx["bus"].close()
    await ctx["graph_store"].close()
    await ctx["vector_index"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: list[Any] = []
    cron_jobs = [
        # Short, fixed poll -- both the graph-write saga and outbox latency should
        # be seconds, not minutes (docs/design/phase-1/02-knowledge-engine.md §17).
        cron(arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
        # Off the write path by design (§10); every 30s keeps semantic search
        # reasonably fresh without hammering a local Ollama instance.
        cron(arq_run_embedding_pass, second={5, 35}),
        # §6: fixed interval for Phase 1, matching Memory Engine's
        # consolidation_worker's own accepted tradeoff.
        cron(
            arq_run_maintenance,
            hour=set(range(0, 24, _SETTINGS.maintenance_interval_hours)),
            minute=0,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_SETTINGS.redis_url)

"""Arq `WorkerSettings` -- run via `arq nova_memory_engine.workers.WorkerSettings`.

Wires the same ports (`MemoryRepository`, `VectorIndex`, `EmbeddingProvider`,
`EventBus`) as `main.py`'s FastAPI app; workers and the API are two deployments of
the same domain logic, matching the embedded-vs-standalone distinction
(docs/architecture/03-backend-architecture.md §2) applied at the process level --
`standalone` mode runs this as its own `arq` process, and nothing here prevents a
future `embedded` mode from driving the same cron schedule in-process instead.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger

from nova_memory_engine.config import Settings
from nova_memory_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_memory_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_memory_engine.observability import create_metrics
from nova_memory_engine.repository.db import create_engine, create_session_factory
from nova_memory_engine.repository.postgres_memory_repository import PostgresMemoryRepository
from nova_memory_engine.workers.consolidation_worker import (
    arq_run_consolidation,
    arq_run_short_term_expiry,
)
from nova_memory_engine.workers.embedding_worker import arq_run_embedding_pass
from nova_memory_engine.workers.outbox_worker import arq_run_outbox_dispatch

_SETTINGS = Settings()
logger = get_logger("memory-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    from nova_embeddings_sdk.factory import get_embedding_provider
    from nova_vectorstore_sdk.backends.pgvector import PgVectorCollection, PgVectorStore

    # A separate OS process from the FastAPI app (docs/architecture/03 §2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("memory-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("memory-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    vector_index = PgVectorStore(
        dsn=_SETTINGS.vector_store_dsn(),
        collections={
            "memory_records": PgVectorCollection(
                table="memory.memory_record", metadata_columns=("embedding_model",)
            )
        },
    )
    await vector_index.connect()

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="memory-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["memory_repository"] = PostgresMemoryRepository(session_factory)
    ctx["vector_index"] = vector_index
    ctx["embedding_provider"] = get_embedding_provider()
    ctx["embedding_model"] = _SETTINGS.embedding_model
    ctx["bus"] = bus
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("memory-engine worker shutting down")
    await ctx["bus"].close()
    await ctx["vector_index"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: list[Any] = []
    cron_jobs = [
        # Short, fixed poll -- outbox latency should be seconds, not minutes.
        cron(arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
        # Off the write path by design (docs/design/phase-1/01-memory-engine.md
        # §10); every 30s keeps semantic search reasonably fresh without hammering
        # a local Ollama instance.
        cron(arq_run_embedding_pass, second={5, 35}),
        # docs/design/phase-1/01-memory-engine.md §6: fixed interval for Phase 1.
        cron(
            arq_run_consolidation,
            hour=set(range(0, 24, _SETTINGS.consolidation_interval_hours)),
            minute=0,
        ),
        # docs/design/phase-1/01-memory-engine.md §4: "Expiry is enforced by
        # workers/consolidation_worker.py, not a Postgres-native TTL" -- separate
        # from arq_run_consolidation because short-term TTLs (hours-to-days) are
        # far tighter than consolidation's multi-hour cycle.
        cron(
            arq_run_short_term_expiry,
            minute=set(range(0, 60, _SETTINGS.short_term_expiry_check_interval_minutes)),
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_SETTINGS.redis_url)

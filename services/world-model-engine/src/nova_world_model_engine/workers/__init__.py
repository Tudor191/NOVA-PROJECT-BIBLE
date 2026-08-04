"""Arq `WorkerSettings` -- run via `arq nova_world_model_engine.workers.WorkerSettings`.

Wires the same ports (`WorldHistoryRepository`, `ContextRepository`,
`GraphStore`, `EventBus`) as `main.py`'s FastAPI app; workers and the API are
two deployments of the same domain logic, matching the embedded-vs-standalone
distinction (docs/architecture/03-backend-architecture.md §2) applied at the
process level.

`ctx["known_user_ids"]` is deliberately always empty in Phase 1 -- there is no
user-directory port yet (see `snapshot_worker.py`/`prediction_worker.py`'s
docstrings and the README's Known Limitations). Both cron jobs run and log
normally, they simply have nothing to iterate until a real user feed exists;
this is honest inertness, not a silent failure.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger

from nova_world_model_engine.config import Settings
from nova_world_model_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_world_model_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_world_model_engine.observability import create_metrics
from nova_world_model_engine.repository.db import create_engine, create_session_factory
from nova_world_model_engine.repository.postgres_history_repository import (
    PostgresHistoryRepository,
)
from nova_world_model_engine.workers.outbox_worker import arq_run_outbox_dispatch
from nova_world_model_engine.workers.prediction_worker import arq_run_predictions
from nova_world_model_engine.workers.snapshot_worker import arq_run_scheduled_snapshots

_SETTINGS = Settings()
logger = get_logger("world-model-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    from nova_graphstore_sdk.factory import get_graph_store
    from redis.asyncio import Redis

    from nova_world_model_engine.repository.redis_context_repository import (
        RedisContextRepository,
    )

    # A separate OS process from the FastAPI app (docs/architecture/03 §2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("world-model-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("world-model-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    redis_client = Redis.from_url(_SETTINGS.redis_url)

    graph_store = get_graph_store()
    await graph_store.connect()

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="world-model-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["history_repository"] = PostgresHistoryRepository(session_factory)
    ctx["redis_client"] = redis_client
    ctx["context_repository"] = RedisContextRepository(redis_client)
    ctx["graph_store"] = graph_store
    ctx["bus"] = bus
    ctx["known_user_ids"] = []  # see module docstring
    ctx["graph_write_degraded_threshold_minutes"] = (
        _SETTINGS.graph_write_degraded_threshold_minutes
    )
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("world-model-engine worker shutting down")
    await ctx["bus"].close()
    await ctx["graph_store"].close()
    await ctx["redis_client"].aclose()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: list[Any] = []
    cron_jobs = [
        # Short, fixed poll -- both the graph-write saga and outbox latency
        # should be seconds, not minutes (docs/design/phase-1/
        # 03-world-model-engine.md §17).
        cron(arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
        # §2: fixed interval for Phase 1, matching Memory/Knowledge Engine's
        # own accepted fixed-interval tradeoff.
        cron(
            arq_run_scheduled_snapshots,
            hour=set(range(0, 24, _SETTINGS.snapshot_interval_hours)),
            minute=0,
        ),
        # §7/§20: structural heuristic, run on the same cadence as snapshots
        # (no independent latency requirement of its own).
        cron(
            arq_run_predictions,
            hour=set(range(0, 24, _SETTINGS.snapshot_interval_hours)),
            minute=5,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_SETTINGS.redis_url)

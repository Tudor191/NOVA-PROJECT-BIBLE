"""Arq `WorkerSettings` -- run via `arq nova_executive_cognition_engine.workers.WorkerSettings`.

Wires the same `ExecutiveRepository` and `EventBus` as `main.py`'s FastAPI
app; workers and the API are two deployments of the same domain logic,
matching the embedded-vs-standalone distinction (docs/architecture/03-
backend-architecture.md §2) applied at the process level. This engine's
outbox is currently its only worker job -- no health/benchmark cron
equivalents exist here (§20). Unlike Reasoning Engine's own worker, no
upstream client ports are wired here: `domain.coordinate.arbitrate_request`
only calls `GoalsPort` and `ExecutiveRepository` (§4), and arbitration
itself only ever runs inside a served RPC handler (`api/`, `events/`), never
from a worker job.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger
from nova_service_kit import create_engine, create_session_factory

from nova_executive_cognition_engine.config import Settings
from nova_executive_cognition_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_executive_cognition_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_executive_cognition_engine.observability import create_metrics
from nova_executive_cognition_engine.repository.postgres_executive_repository import (
    PostgresExecutiveRepository,
)
from nova_executive_cognition_engine.workers.outbox_worker import arq_run_outbox_dispatch

_SETTINGS = Settings()
logger = get_logger("executive-cognition-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    # A separate OS process from the FastAPI app (docs/architecture/03 §2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("executive-cognition-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("executive-cognition-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    bus = bind_event_bus(
        "executive-cognition-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["repository"] = PostgresExecutiveRepository(session_factory)
    ctx["bus"] = bus
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("executive-cognition-engine worker shutting down")
    await ctx["bus"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: list[Any] = []
    cron_jobs = [
        # Short, fixed poll -- outbox latency should be seconds, not minutes.
        cron(arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_SETTINGS.redis_url)

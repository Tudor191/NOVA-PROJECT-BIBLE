"""Arq `WorkerSettings` -- run via `arq nova_perception_engine.workers.WorkerSettings`.

Wires the same `PerceptionRepository` and `EventBus` as `main.py`'s FastAPI
app; workers and the API are two deployments of the same domain logic,
matching the embedded-vs-standalone distinction (docs/architecture/
03-backend-architecture.md Sec2) applied at the process level. This engine's
outbox is currently its only worker job -- sensor state and live fusion
state live only inside the FastAPI process (Sec4.1's own in-memory,
restart-safe-to-lose `IdentityConfidenceState` admission).
"""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger
from nova_service_kit import (
    create_engine,
    create_session_factory,
    service_cron,
    worker_queue_name,
)

from nova_perception_engine.config import Settings
from nova_perception_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_perception_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_perception_engine.observability import create_metrics
from nova_perception_engine.repository.postgres_perception_repository import (
    PostgresPerceptionRepository,
)
from nova_perception_engine.workers.outbox_worker import arq_run_outbox_dispatch

_SERVICE_NAME = "perception-engine"
"""This worker's own engine identity, single-sourced.

It names three things that must never drift apart: the Event Bus binding
below, the arq queue this worker exclusively owns, and the arq job names its
cron ticks are enqueued under. Sharing arq's global default queue and a
coroutine-derived cron name is what let one engine's worker consume and
discard another's scheduled jobs -- see `nova_service_kit.worker`."""

_SETTINGS = Settings()
logger = get_logger("perception-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    # A separate OS process from the FastAPI app (docs/architecture/03 Sec2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("perception-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("perception-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    bus = bind_event_bus(
        _SERVICE_NAME,
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["repository"] = PostgresPerceptionRepository(session_factory)
    ctx["bus"] = bus
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("perception-engine worker shutting down")
    await ctx["bus"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    # This worker is the sole enqueuer and sole consumer of its own scheduled
    # jobs. Without an explicit queue it would share arq's global `arq:queue`
    # with every other engine's worker and consume whichever job it reached
    # first (`nova_service_kit.worker`).
    queue_name = worker_queue_name(_SERVICE_NAME)
    functions: list[Any] = []
    cron_jobs = [
        # Short, fixed poll -- outbox latency should be seconds, not minutes.
        service_cron(_SERVICE_NAME, arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_SETTINGS.redis_url)

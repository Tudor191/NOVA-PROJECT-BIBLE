"""Arq `WorkerSettings` -- run via `arq nova_ai_model_orchestration_engine.workers.WorkerSettings`.

Wires the same ports (`ModelRegistryRepository`, `UsageRepository`,
`ConnectorFactory`, `EventBus`) as `main.py`'s FastAPI app; workers and the API
are two deployments of the same domain logic, matching the embedded-vs-
standalone distinction (docs/architecture/03-backend-architecture.md §2)
applied at the process level.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger
from nova_service_kit import create_engine, create_session_factory

from nova_ai_model_orchestration_engine.config import Settings
from nova_ai_model_orchestration_engine.connectors.factory import ConnectorFactory
from nova_ai_model_orchestration_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_ai_model_orchestration_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_ai_model_orchestration_engine.observability import create_metrics
from nova_ai_model_orchestration_engine.repository.postgres_registry_repository import (
    PostgresModelRegistryRepository,
)
from nova_ai_model_orchestration_engine.repository.postgres_usage_repository import (
    PostgresUsageRepository,
)
from nova_ai_model_orchestration_engine.workers.benchmark_worker import arq_run_benchmarks
from nova_ai_model_orchestration_engine.workers.health_monitor_worker import arq_run_health_checks
from nova_ai_model_orchestration_engine.workers.outbox_worker import arq_run_outbox_dispatch

_SETTINGS = Settings()
logger = get_logger("ai-model-orchestration-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    # A separate OS process from the FastAPI app (docs/architecture/03 §2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("ai-model-orchestration-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("ai-model-orchestration-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    bus = bind_event_bus(
        "ai-model-orchestration-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["registry_repository"] = PostgresModelRegistryRepository(session_factory)
    ctx["usage_repository"] = PostgresUsageRepository(session_factory)
    ctx["connector_factory"] = ConnectorFactory(
        ollama_base_url=_SETTINGS.ollama_base_url,
        anthropic_api_key=_SETTINGS.anthropic_api_key or None,
        timeout_s=_SETTINGS.connector_timeout_s,
    )
    ctx["bus"] = bus
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ai-model-orchestration-engine worker shutting down")
    await ctx["bus"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: list[Any] = []
    cron_jobs = [
        # Short, fixed poll -- outbox latency should be seconds, not minutes.
        cron(arq_run_outbox_dispatch, second={0, 10, 20, 30, 40, 50}),
        # §2: fixed interval, Phase 2A's own accepted fixed-interval tradeoff.
        cron(
            arq_run_health_checks,
            second=set(range(0, 60, _SETTINGS.health_check_interval_seconds)),
        ),
        cron(
            arq_run_benchmarks,
            hour=set(range(0, 24, _SETTINGS.benchmark_interval_hours)),
            minute=0,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_SETTINGS.redis_url)

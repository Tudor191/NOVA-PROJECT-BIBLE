"""Arq `WorkerSettings` -- run via `arq nova_reasoning_engine.workers.WorkerSettings`.

Wires the same ports (six upstream Protocols, `ReasoningRepository`,
`EventBus`) as `main.py`'s FastAPI app; workers and the API are two
deployments of the same domain logic, matching the embedded-vs-standalone
distinction (docs/architecture/03-backend-architecture.md §2) applied at the
process level. This engine's outbox is currently its only worker job -- no
health/benchmark cron equivalents exist here (§20).
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger
from nova_service_kit import create_engine, create_session_factory

from nova_reasoning_engine.clients.goals_client import GoalsClient
from nova_reasoning_engine.clients.knowledge_client import KnowledgeClient
from nova_reasoning_engine.clients.memory_client import MemoryClient
from nova_reasoning_engine.clients.model_orchestration_client import ModelOrchestrationClient
from nova_reasoning_engine.clients.personal_context_client import PersonalContextClient
from nova_reasoning_engine.clients.world_model_client import WorldModelClient
from nova_reasoning_engine.config import Settings
from nova_reasoning_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_reasoning_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_reasoning_engine.observability import create_metrics
from nova_reasoning_engine.repository.postgres_reasoning_repository import (
    PostgresReasoningRepository,
)
from nova_reasoning_engine.workers.outbox_worker import arq_run_outbox_dispatch

_SETTINGS = Settings()
logger = get_logger("reasoning-engine-worker")


async def startup(ctx: dict[str, Any]) -> None:
    # A separate OS process from the FastAPI app (docs/architecture/03 §2's
    # standalone mode) needs its own observability setup -- `main.py`'s
    # `configure_observability()` call doesn't reach this process.
    configure_observability("reasoning-engine-worker", log_level=_SETTINGS.log_level)
    logger.info("reasoning-engine worker starting")

    engine = create_engine(_SETTINGS.postgres_dsn)
    session_factory = create_session_factory(engine)

    bus = bind_event_bus(
        "reasoning-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    await bus.connect()

    world_model_client = WorldModelClient(bus)

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["repository"] = PostgresReasoningRepository(session_factory)
    ctx["memory_port"] = MemoryClient(bus)
    ctx["knowledge_port"] = KnowledgeClient(bus)
    ctx["world_model_port"] = world_model_client
    ctx["personal_context_port"] = PersonalContextClient(world_model_client)
    ctx["goals_port"] = GoalsClient(bus)
    ctx["model_orchestration_port"] = ModelOrchestrationClient(bus)
    ctx["bus"] = bus
    ctx["metrics"] = create_metrics()  # must follow configure_observability, above


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("reasoning-engine worker shutting down")
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

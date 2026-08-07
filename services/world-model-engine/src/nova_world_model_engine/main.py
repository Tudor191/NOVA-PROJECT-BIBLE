"""world-model-engine's FastAPI entrypoint -- wires every port
(`WorldHistoryRepository`, `ContextRepository`, `GraphStore`, the Event Bus) to
their concrete implementations, and registers the request/reply server and
event subscriptions declared in `events/subscribed.py`. `workers/__init__.py`
wires the same ports for the separate Arq worker process
(docs/architecture/03-backend-architecture.md §2's embedded-vs-standalone
distinction, applied to workers).

`create_app` accepts each port as an optional override so tests can inject
fakes without needing real Postgres/Redis/Neo4j reachable -- real infra is
only constructed for whichever port isn't supplied (mirrors Memory/Knowledge
Engine's `main.py`).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import FastAPI
from nova_contracts import ContextReplyPayload, ContextRequestPayload, EventEnvelope
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_world_model_engine.api.context import router as context_router
from nova_world_model_engine.api.graph import router as graph_router
from nova_world_model_engine.api.health import router as health_router
from nova_world_model_engine.api.objects import router as objects_router
from nova_world_model_engine.api.snapshots import router as snapshots_router
from nova_world_model_engine.config import Settings
from nova_world_model_engine.domain import context as context_domain
from nova_world_model_engine.domain.ports import (
    ContextRepository,
    GraphStore,
    WorldHistoryRepository,
)
from nova_world_model_engine.events import handlers
from nova_world_model_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_world_model_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_world_model_engine.observability import create_metrics

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("world-model-engine")


def _make_context_request_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> ContextReplyPayload:
        state = app.state
        payload = ContextRequestPayload.model_validate(envelope.payload)
        start = time.perf_counter()
        try:
            context = await context_domain.get_context(state.context_repository, payload.user_id)
        except Exception:
            state.metrics.context_degraded_total.add(1)
            state.metrics.context_request_duration_seconds.record(time.perf_counter() - start)
            logger.warning("world_model.context.request degraded", exc_info=True)
            return ContextReplyPayload(user_id=payload.user_id, degraded=True)
        state.metrics.context_request_duration_seconds.record(time.perf_counter() - start)
        state.metrics.context_requests_total.add(1)

        if context is None:
            return ContextReplyPayload(user_id=payload.user_id, confidence=None, degraded=False)
        scoped = context_domain.scoped_view(context, scope=payload.scope)
        return ContextReplyPayload(
            user_id=payload.user_id,
            objective=scoped.get("objective"),
            project_id=UUID(scoped["project_id"]) if scoped.get("project_id") else None,
            device=scoped.get("device"),
            task=scoped.get("task"),
            activity=scoped.get("activity"),
            confidence=scoped.get("confidence"),
            updated_at=datetime.fromisoformat(scoped["updated_at"])
            if scoped.get("updated_at")
            else None,
            degraded=False,
        )

    return handle


def create_app(
    settings: Settings | None = None,
    *,
    context_repository: ContextRepository | None = None,
    history_repository: WorldHistoryRepository | None = None,
    graph_store: GraphStore | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("world-model-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="world-model-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("world-model-engine starting")

        engine: AsyncEngine | None = None
        history_repo = history_repository
        if history_repo is None:
            from nova_world_model_engine.repository.db import create_engine, create_session_factory
            from nova_world_model_engine.repository.postgres_history_repository import (
                PostgresHistoryRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            history_repo = PostgresHistoryRepository(create_session_factory(engine))

        redis_client: Redis | None = None
        context_repo = context_repository
        if context_repo is None:
            from redis.asyncio import Redis as RedisClient

            from nova_world_model_engine.repository.redis_context_repository import (
                RedisContextRepository,
            )

            redis_client = RedisClient.from_url(settings.redis_url)
            context_repo = RedisContextRepository(redis_client)

        gstore = graph_store
        if gstore is None:
            from nova_graphstore_sdk.factory import get_graph_store

            gstore = get_graph_store()
        await gstore.connect()

        await bus.connect()
        await bus.serve(
            "world_model.context.request",
            _make_context_request_handler(app),
            source_engine="world-model-engine",
        )
        await bus.subscribe(
            "perception.*.observed",
            handlers.make_perception_dispatch_handler(context_repo, history_repo),
        )
        await bus.subscribe("action.result", handlers.make_action_result_handler(history_repo))
        await bus.subscribe("agent_os.task.*", handlers.make_agent_os_task_handler())
        await bus.subscribe("nova.mode.changed", handlers.make_mode_changed_handler())

        app.state.settings = settings
        app.state.context_repository = context_repo
        app.state.history_repository = history_repo
        app.state.graph_store = gstore
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.ready = True
        yield
        logger.info("world-model-engine shutting down")
        app.state.ready = False
        await bus.close()
        await gstore.close()
        if redis_client is not None:
            await redis_client.aclose()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="world-model-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(context_router)
    fastapi_app.include_router(objects_router)
    fastapi_app.include_router(graph_router)
    fastapi_app.include_router(snapshots_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

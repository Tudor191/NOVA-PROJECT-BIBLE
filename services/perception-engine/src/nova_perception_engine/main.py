"""perception-engine's FastAPI entrypoint -- wires `PerceptionRepository`,
the Event Bus, `AIModelOrchestrationClient` (the sole legal path to a
wake/voiceprint/faceprint/gaze model, ADR-020), the two shipped sensors
(`VoiceSensor`, `CameraSensor`), and `SessionActivityTracker` to their
concrete implementations (docs/design/phase-2d/03-perception-engine.md §1).

Per §13.1, this engine serves no synchronous Event-Bus RPC this phase --
`bus.subscribe` (not `bus.serve`) is the only inbound wiring, against
`communication.session.created`/`.completed` (§13.3).

Sensor registration ("Register Sensor" in Bible Part 11's own API list) is a
startup-time configuration concern this phase, not a runtime API endpoint
(§14) -- the two sensors below are constructed and `initialize()`d here,
never through a public HTTP call.

`create_app` accepts `repository` and `ai_model_port` as optional overrides so
tests can inject fakes without needing real Postgres or a live
`ai-model-orchestration-engine` reachable over the bus -- real infra is only
constructed when it isn't supplied (mirrors every other engine's `main.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import bind_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_perception_engine.api.consent import router as consent_router
from nova_perception_engine.api.identities import router as identities_router
from nova_perception_engine.api.sensors import router as sensors_router
from nova_perception_engine.clients.ai_model_orchestration_client import (
    AIModelOrchestrationClient,
)
from nova_perception_engine.config import Settings
from nova_perception_engine.domain.ports import AIModelOrchestrationPort, PerceptionRepository
from nova_perception_engine.domain.session_activity import SessionActivityTracker
from nova_perception_engine.events.handlers import make_session_dispatch_handler
from nova_perception_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_perception_engine.events.subscribed import SUBSCRIBABLE_SUBJECTS
from nova_perception_engine.observability import create_metrics
from nova_perception_engine.sensors.camera_sensor import CameraSensor
from nova_perception_engine.sensors.voice_sensor import VoiceSensor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("perception-engine")


def create_app(
    settings: Settings | None = None,
    *,
    repository: PerceptionRepository | None = None,
    ai_model_port: AIModelOrchestrationPort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("perception-engine", log_level=settings.log_level)
    metrics = create_metrics()  # must follow configure_observability -- see observability.py

    bus = bind_event_bus(
        "perception-engine",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    ai_model_port = ai_model_port or AIModelOrchestrationClient(
        bus, timeout_ms=settings.ai_model_orchestration_timeout_ms
    )
    session_tracker = SessionActivityTracker()
    encryption_key = settings.template_encryption_key.encode("utf-8")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("perception-engine starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_perception_engine.repository.postgres_perception_repository import (
                PostgresPerceptionRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresPerceptionRepository(session_factory)

        voice_sensor = VoiceSensor(
            repository=repo, ai_model_port=ai_model_port, encryption_key=encryption_key
        )
        camera_sensor = CameraSensor(
            repository=repo, ai_model_port=ai_model_port, encryption_key=encryption_key
        )
        await voice_sensor.initialize()
        await voice_sensor.start()
        await camera_sensor.initialize()
        await camera_sensor.start()

        await bus.connect()
        await bus.subscribe(
            "communication.session.created", make_session_dispatch_handler(session_tracker)
        )
        await bus.subscribe(
            "communication.session.completed", make_session_dispatch_handler(session_tracker)
        )

        app.state.settings = settings
        app.state.repository = repo
        app.state.bus = bus
        app.state.metrics = metrics
        app.state.ai_model_port = ai_model_port
        app.state.session_tracker = session_tracker
        app.state.sensors_by_id = {
            voice_sensor.sensor_id: voice_sensor,
            camera_sensor.sensor_id: camera_sensor,
        }
        app.state.sensors_by_source = {"microphone": voice_sensor, "camera": camera_sensor}
        app.state.ready = True

        yield
        logger.info("perception-engine shutting down")
        app.state.ready = False
        # A sensor may already be `stopped` (consent revoked mid-session,
        # §3.3) -- `stop()` from a non-running/paused state is an illegal
        # transition (domain/sensor.py's own state machine, §5), so shutdown
        # guards it the same way `api/consent.py`'s revocation handler does.
        for sensor in (voice_sensor, camera_sensor):
            if sensor.state() in ("running", "paused"):
                await sensor.stop()
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="perception-engine", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.include_router(identities_router)
    fastapi_app.include_router(consent_router)
    fastapi_app.include_router(sensors_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

"""nova_agent_os_registry's FastAPI entrypoint -- health/readiness/metrics
only (TDD 3E §5: `agent-os/registry` is control-plane infrastructure, not
a `/v1/...` request/reply service). At startup, discovers every Agent
Package under `agents/` (doc 12 §6/§15's filesystem-based discovery) and
runs the real 8-step install pipeline (`domain/pipeline.py`) for each --
Phase 3E Milestone 3 ships no real Agent Packages yet (none of the five
named agents exist), so this loop is a real, exercised no-op until the
first one is scaffolded.

`create_app` accepts each port as an optional override so tests can
inject fakes without needing real Postgres reachable -- mirrors every
other engine's `main.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nova_eventbus_sdk import BoundEventBus, get_event_bus
from nova_observability import configure_observability, get_logger, prometheus_asgi_app
from nova_service_kit import make_health_router

from nova_agent_os_registry.clients.communication_client import CommunicationClient
from nova_agent_os_registry.config import Settings
from nova_agent_os_registry.domain.discovery import discover_agent_packages
from nova_agent_os_registry.domain.pipeline import InstallationError, install_agent_package
from nova_agent_os_registry.domain.ports import CommunicationPort, RegistryRepository
from nova_agent_os_registry.events.published import PUBLISHABLE_SUBJECTS
from nova_agent_os_registry.events.subscribed import SUBSCRIBABLE_SUBJECTS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("registry")


async def _install_discovered_packages(
    settings: Settings,
    *,
    repository: RegistryRepository,
    communication_port: CommunicationPort,
) -> None:
    discovered = discover_agent_packages(Path(settings.agents_root))
    for package in discovered:
        try:
            installed = await install_agent_package(
                package,
                repository=repository,
                communication_port=communication_port,
                primary_user_id=settings.primary_user_id,
                kernel_version=settings.kernel_version,
            )
        except InstallationError as exc:
            logger.error(
                "agent package under %s failed installation at stage %s: %s",
                package.directory,
                exc.stage.value,
                exc,
            )
            continue
        logger.info(
            "installed agent package %s@%s (health_status=%s)",
            installed.id,
            installed.version,
            installed.health_status,
        )


def create_app(
    settings: Settings | None = None,
    *,
    repository: RegistryRepository | None = None,
    communication_port: CommunicationPort | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_observability("registry", log_level=settings.log_level)

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="registry",
        publishable_subjects=PUBLISHABLE_SUBJECTS,
        subscribable_subjects=SUBSCRIBABLE_SUBJECTS,
    )
    if communication_port is None:
        communication_port = CommunicationClient(bus)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("registry starting")

        engine: AsyncEngine | None = None
        repo = repository
        if repo is None:
            from nova_service_kit import create_engine, create_session_factory

            from nova_agent_os_registry.repository.postgres_registry_repository import (
                PostgresRegistryRepository,
            )

            engine = create_engine(settings.postgres_dsn)
            session_factory = create_session_factory(engine)
            repo = PostgresRegistryRepository(session_factory)

        app.state.settings = settings
        app.state.repository = repo
        app.state.bus = bus

        await bus.connect()
        await _install_discovered_packages(
            settings, repository=repo, communication_port=communication_port
        )

        app.state.ready = True
        yield
        logger.info("registry shutting down")
        app.state.ready = False
        await bus.close()
        if engine is not None:
            await engine.dispose()

    fastapi_app = FastAPI(title="registry", version="0.1.0", lifespan=lifespan)
    fastapi_app.include_router(make_health_router())
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

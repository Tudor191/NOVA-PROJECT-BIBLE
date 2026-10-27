"""Shared fixtures: the real FastAPI app, backed by fakes.

The app is the **real** one -- `create_app` with its real routers, real
schemas and real lifespan. Only the two ports are substituted, which is the
ADR-033 default tier: no Docker, no Postgres, no event bus, but every line of
routing and serialization exercised.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.main import create_app

from tests.fakes.repository import FakeAutonomyRepository
from tests.fakes.trust_source import SpyTrustSource, StubTrustSource

__all__ = ["StubTrustSource"]


@pytest.fixture(autouse=True)
def _in_memory_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default tier boots the real app, and `create_app` binds a real
    `BoundEventBus`. Without this the bus would default to NATS and
    `bus.connect()` would block on an unreachable broker -- the same
    `EVENT_BUS_BACKEND=in_memory` every other engine's tests set.

    This engine publishes and subscribes to nothing (D-4D-1), so the bus is
    never used; it still has to *connect* because the lifespan binds it, which
    is the point of binding it at all (`main.py`)."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def repository() -> FakeAutonomyRepository:
    return FakeAutonomyRepository()


@pytest.fixture
def trust_source() -> SpyTrustSource:
    """Defaults to `NO_DATA` -- the honest answer for a user with no completed
    sessions, and the one that keeps every score `None` unless a test opts in
    to evidence."""
    return SpyTrustSource()


@pytest.fixture
def app(
    settings: Settings,
    repository: FakeAutonomyRepository,
    trust_source: SpyTrustSource,
) -> FastAPI:
    return create_app(settings, repository=repository, trust_source=trust_source)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client

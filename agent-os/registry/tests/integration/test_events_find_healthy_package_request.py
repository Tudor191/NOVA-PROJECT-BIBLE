"""A real Event Bus round-trip through `main.py`'s served
`agent_os.registry.find_healthy_package.request` RPC (disclosed addition,
see `events/find_healthy_package_handler.py`'s own docstring) -- mirrors
`planning-engine`'s own `test_events_decompose_request.py` convention
exactly (the closest, most recent precedent for a served request/reply RPC
in this codebase).

`app.state.bus`'s own `publishable_subjects` deliberately do not include
this subject -- Registry only ever *serves* it, never calls it on itself. A
second `BoundEventBus`, wrapping the exact same underlying in-memory bus
instance, stands in for the real external caller (`agent-os/kernel`'s own
Scheduler).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nova_agent_os_registry.config import Settings
from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.main import create_app
from nova_contracts import (
    AgentOsFindHealthyPackageReplyPayload,
    AgentOsFindHealthyPackageRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.repository import FakeRegistryRepository


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({"agent_os.registry.find_healthy_package.request"}),
        subscribable_subjects=frozenset(),
    )


def _package(**overrides: object) -> AgentPackage:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "category": "research",
        "version": "0.1.0",
        "manifest_json": {"id": "research-agent", "version": "0.1.0"},
        "installed_at": datetime.now(UTC),
        "health_status": "healthy",
        "checksum": "a" * 64,
    }
    defaults.update(overrides)
    return AgentPackage(**defaults)


async def test_find_healthy_package_returns_the_installed_healthy_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeRegistryRepository()
    package = _package()
    repository.rows[(package.category, package.version)] = package
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsFindHealthyPackageRequestPayload(
            category="research", requesting_engine="test-caller-engine", correlation_id=uuid4()
        )
        reply_envelope = await caller_bus.request(
            "agent_os.registry.find_healthy_package.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsFindHealthyPackageReplyPayload.model_validate(reply_envelope.payload)

    assert result.package is not None
    assert result.package.id == package.id
    assert result.package.category == "research"
    assert result.package.version == "0.1.0"
    assert result.package.manifest_json["id"] == "research-agent"
    assert result.package.health_status == "healthy"


async def test_find_healthy_package_returns_none_for_an_unknown_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeRegistryRepository())

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsFindHealthyPackageRequestPayload(
            category="unknown-category",
            requesting_engine="test-caller-engine",
            correlation_id=uuid4(),
        )
        reply_envelope = await caller_bus.request(
            "agent_os.registry.find_healthy_package.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsFindHealthyPackageReplyPayload.model_validate(reply_envelope.payload)

    assert result.package is None


async def test_find_healthy_package_excludes_a_non_healthy_installed_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeRegistryRepository()
    package = _package(health_status="unhealthy")
    repository.rows[(package.category, package.version)] = package
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsFindHealthyPackageRequestPayload(
            category="research", requesting_engine="test-caller-engine", correlation_id=uuid4()
        )
        reply_envelope = await caller_bus.request(
            "agent_os.registry.find_healthy_package.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsFindHealthyPackageReplyPayload.model_validate(reply_envelope.payload)

    assert result.package is None

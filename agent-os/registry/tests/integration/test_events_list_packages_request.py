"""A real Event Bus round-trip through `main.py`'s served
`agent_os.registry.list_packages.request` RPC (Phase 4C milestone 4C.2a).

Mirrors `test_events_find_healthy_package_request.py` exactly, including the
second-`BoundEventBus` caller stand-in: `app.state.bus`'s own
`publishable_subjects` deliberately do not include this subject -- Registry
only ever *serves* it -- so a separate bus wrapping the same in-memory broker
plays the real external caller (`agent-os/kernel`'s `RegistryClient`).

The property this file is really about is the one `find_healthy_package`
cannot hold: **a listing reports what is installed, including the rows the
dispatch RPC filters out.** Every test below that asserts an unhealthy or
superseded version is present is asserting exactly that difference.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from nova_agent_os_registry.config import Settings
from nova_agent_os_registry.domain.models import AgentPackage
from nova_agent_os_registry.main import create_app
from nova_contracts import (
    AgentOsListPackagesReplyPayload,
    AgentOsListPackagesRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus
from pydantic import ValidationError

from tests.fakes.repository import FakeRegistryRepository

_SUBJECT = "agent_os.registry.list_packages.request"


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({_SUBJECT}),
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


async def _list(app) -> AgentOsListPackagesReplyPayload:  # type: ignore[no-untyped-def]
    caller_bus = _caller_bus(app)
    reply_envelope = await caller_bus.request(
        _SUBJECT,
        AgentOsListPackagesRequestPayload(
            requesting_engine="test-caller-engine", correlation_id=uuid4()
        ),
        source_engine="test-caller-engine",
    )
    return AgentOsListPackagesReplyPayload.model_validate(reply_envelope.payload)


async def test_returns_every_installed_package_with_all_snapshot_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeRegistryRepository()
    package = _package()
    repository.rows[(package.category, package.version)] = package
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        result = await _list(app)

    assert len(result.packages) == 1
    snapshot = result.packages[0]
    assert snapshot.id == package.id
    assert snapshot.category == "research"
    assert snapshot.version == "0.1.0"
    assert snapshot.manifest_json["id"] == "research-agent"
    assert snapshot.health_status == "healthy"


async def test_returns_an_empty_list_when_nothing_is_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Healthy Registry, nothing installed. This is a successful reply, not
    an error -- decision D-1's `200 []` case, established here at the RPC
    layer where the distinction originates."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeRegistryRepository())

    async with app.router.lifespan_context(app):
        result = await _list(app)

    assert result.packages == []


async def test_includes_packages_the_dispatch_rpc_would_filter_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole reason this RPC exists.

    `find_healthy_package` applies `select_dispatch_version` and would answer
    `None` for a category whose only row is unhealthy. A listing that did the
    same would tell an operator nothing is installed at the moment they most
    need to see that something is installed and broken.
    """
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeRegistryRepository()
    unhealthy = _package(category="qa", version="0.1.0", health_status="unhealthy")
    repository.rows[("qa", "0.1.0")] = unhealthy
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        result = await _list(app)

    assert [package.category for package in result.packages] == ["qa"]
    assert result.packages[0].health_status == "unhealthy"


async def test_includes_every_coexisting_version_not_only_the_dispatch_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeRegistryRepository()
    for version in ("1.1.0", "1.2.0"):
        repository.rows[("coding", version)] = _package(
            category="coding",
            version=version,
            manifest_json={"id": "coding-agent", "version": version},
        )
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        result = await _list(app)

    assert [package.version for package in result.packages] == ["1.1.0", "1.2.0"]


async def test_ordering_is_deterministic_and_independent_of_insertion_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inserted deliberately out of order. The reply must come back in the
    repository's declared `(category, version, id)` order regardless."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeRegistryRepository()
    for category, version in (
        ("qa", "0.1.0"),
        ("architect", "0.2.0"),
        ("architect", "0.1.0"),
        ("coding", "0.1.0"),
    ):
        repository.rows[(category, version)] = _package(category=category, version=version)
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        result = await _list(app)

    assert [(p.category, p.version) for p in result.packages] == [
        ("architect", "0.1.0"),
        ("architect", "0.2.0"),
        ("coding", "0.1.0"),
        ("qa", "0.1.0"),
    ]


async def test_a_malformed_request_is_rejected_rather_than_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler validates the request even though it reads no field from
    it. Answering an unparseable request would make the contract advisory.

    The raised error is asserted to name the missing field, so this cannot
    pass on some unrelated failure. Negative control run: deleting the
    handler's `model_validate` call makes this test fail with DID NOT RAISE,
    confirming it exercises the handler rather than the SDK's own
    publish-side checks.
    """
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeRegistryRepository())

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        with pytest.raises(ValidationError) as raised:
            await caller_bus.request(
                _SUBJECT,
                # `correlation_id` missing: not a valid request payload.
                AgentOsListPackagesRequestPayload.model_construct(
                    requesting_engine="test-caller-engine"
                ),
                source_engine="test-caller-engine",
            )

    assert "correlation_id" in str(raised.value)


# --- regression: the dispatch RPC is unchanged ------------------------------


async def test_find_healthy_package_still_selects_one_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4C.2a adds a second served subject to the same app. This asserts the
    first one still behaves exactly as it did -- one winner, health-filtered
    -- rather than being affected by the new registration sharing its bus.

    Its own suite in `test_events_find_healthy_package_request.py` covers the
    behaviour in depth; this is the cross-slice regression that would catch a
    `bus.serve` collision or a handler wired to the wrong subject.
    """
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    from nova_contracts import (
        AgentOsFindHealthyPackageReplyPayload,
        AgentOsFindHealthyPackageRequestPayload,
    )

    repository = FakeRegistryRepository()
    repository.rows[("coding", "1.1.0")] = _package(category="coding", version="1.1.0")
    repository.rows[("coding", "1.2.0")] = _package(
        category="coding", version="1.2.0", health_status="unhealthy"
    )
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"agent_os.registry.find_healthy_package.request"}
            ),
            subscribable_subjects=frozenset(),
        )
        reply_envelope = await caller_bus.request(
            "agent_os.registry.find_healthy_package.request",
            AgentOsFindHealthyPackageRequestPayload(
                category="coding",
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        selected = AgentOsFindHealthyPackageReplyPayload.model_validate(
            reply_envelope.payload
        )
        listed = await _list(app)

    # The dispatch RPC still picks exactly one, and still filters on health.
    assert selected.package is not None
    assert selected.package.version == "1.1.0"
    # The listing RPC still reports both. Same app, same bus, two answers.
    assert [package.version for package in listed.packages] == ["1.1.0", "1.2.0"]

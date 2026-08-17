"""A real Event Bus round-trip through `main.py`'s served
`capability.resolve.request`/`capability.invoke.request` RPCs (Fork
3C-1/3D-1, TDD 3C §4/§7) -- every other test exercises this engine's
install pipeline only via `api/capabilities.py`'s HTTP path; this is the
one place the RPC handlers themselves, registered by `create_app`'s
`bus.serve(...)` calls, are actually invoked through a request/reply round
trip rather than called as bare Python functions.

`app.state.bus`'s own `publishable_subjects` (`events/published.py`)
deliberately do not include `capability.resolve.request`/
`capability.invoke.request` -- this engine only ever *serves* those
subjects, never calls them on itself. A second `BoundEventBus`, wrapping
the exact same underlying in-memory bus instance, stands in for the kind
of external caller (`action-engine`'s future `CapabilityPort`/client)
whose own `published.py` would legitimately list them -- mirrors
`executive-cognition-engine`'s own `test_events_arbitrate_request.py`
convention.

`adapters=` is deliberately left unset everywhere here -- `create_app`
then builds the engine's own real adapters (cheap and side-effect-free at
bootstrap-install time, see `domain/pipeline.py`'s own
`_out_of_scope_probe`), so the `filesystem` invoke's sandbox-violation
case below is a genuine, adversarial out-of-scope read against a real
`tmp_path`, never mocked (TDD 3C's own acceptance criterion 2)."""

from __future__ import annotations

from uuid import uuid4

from nova_capability_engine.config import Settings
from nova_capability_engine.main import create_app
from nova_contracts import (
    CapabilityInvokeReplyPayload,
    CapabilityInvokeRequestPayload,
    CapabilityResolveReplyPayload,
    CapabilityResolveRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.repository import FakeCapabilityRepository


async def test_resolve_request_finds_an_installed_capability(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCapabilityRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"capability.resolve.request", "capability.invoke.request"}
            ),
            subscribable_subjects=frozenset(),
        )
        capability = next(iter(repository.capabilities.values()))

        reply_envelope = await caller_bus.request(
            "capability.resolve.request",
            CapabilityResolveRequestPayload(
                capability_id=capability.id,
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = CapabilityResolveReplyPayload.model_validate(reply_envelope.payload)

        assert reply.found is True
        assert reply.capability is not None
        assert reply.capability.id == capability.id


async def test_resolve_request_reports_not_found_for_an_unknown_id(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeCapabilityRepository())

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"capability.resolve.request", "capability.invoke.request"}
            ),
            subscribable_subjects=frozenset(),
        )

        reply_envelope = await caller_bus.request(
            "capability.resolve.request",
            CapabilityResolveRequestPayload(
                capability_id=uuid4(),
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = CapabilityResolveReplyPayload.model_validate(reply_envelope.payload)

        assert reply.found is False
        assert reply.capability is None


async def test_invoke_request_round_trips_a_successful_operation(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    (tmp_path / "note.txt").write_text("hello from the sandbox")
    repository = FakeCapabilityRepository()
    app = create_app(Settings(sandbox_filesystem_root=str(tmp_path)), repository=repository)

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"capability.resolve.request", "capability.invoke.request"}
            ),
            subscribable_subjects=frozenset(),
        )
        filesystem_capability = next(
            c for c in repository.capabilities.values() if c.name == "filesystem"
        )

        reply_envelope = await caller_bus.request(
            "capability.invoke.request",
            CapabilityInvokeRequestPayload(
                capability_id=filesystem_capability.id,
                operation="read",
                parameters={"path": str(tmp_path / "note.txt")},
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = CapabilityInvokeReplyPayload.model_validate(reply_envelope.payload)

        assert reply.outcome == "success"
        assert reply.result == {"content": "hello from the sandbox"}


async def test_invoke_request_reports_a_real_sandbox_violation_for_an_out_of_scope_read(
    tmp_path,  # type: ignore[no-untyped-def]
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    sandboxed_root = tmp_path / "sandboxed"
    sandboxed_root.mkdir()
    outside = tmp_path / "outside_secret.txt"
    outside.write_text("do not read me over RPC")
    repository = FakeCapabilityRepository()
    app = create_app(
        Settings(sandbox_filesystem_root=str(sandboxed_root)), repository=repository
    )

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"capability.resolve.request", "capability.invoke.request"}
            ),
            subscribable_subjects=frozenset(),
        )
        filesystem_capability = next(
            c for c in repository.capabilities.values() if c.name == "filesystem"
        )

        reply_envelope = await caller_bus.request(
            "capability.invoke.request",
            CapabilityInvokeRequestPayload(
                capability_id=filesystem_capability.id,
                operation="read",
                parameters={"path": str(outside)},
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = CapabilityInvokeReplyPayload.model_validate(reply_envelope.payload)

        assert reply.outcome == "sandbox_violation"
        assert reply.result is None
        assert outside.read_text() == "do not read me over RPC"


async def test_invoke_request_for_an_unknown_capability_id_returns_a_structured_failure(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(Settings(), repository=FakeCapabilityRepository())

    async with app.router.lifespan_context(app):
        caller_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001
            engine_name="test-caller-engine",
            publishable_subjects=frozenset(
                {"capability.resolve.request", "capability.invoke.request"}
            ),
            subscribable_subjects=frozenset(),
        )

        reply_envelope = await caller_bus.request(
            "capability.invoke.request",
            CapabilityInvokeRequestPayload(
                capability_id=uuid4(),
                operation="read",
                requesting_engine="test-caller-engine",
                correlation_id=uuid4(),
            ),
            source_engine="test-caller-engine",
        )
        reply = CapabilityInvokeReplyPayload.model_validate(reply_envelope.payload)

        assert reply.outcome == "failure"
        assert reply.error == "capability not found"

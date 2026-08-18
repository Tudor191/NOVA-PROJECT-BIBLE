"""`clients.identity_client.IdentityClient` (TDD 3D §7, ADR-032) -- a real
Event Bus round trip through `world_model.context.request`, reading
`ContextReplyPayload.present_identities`. This engine's own (non-fake)
`IdentityClient`, constructed by `create_app` with no override, calls the
RPC directly -- the wire contract itself is exercised."""

from __future__ import annotations

from uuid import uuid4

from nova_action_engine.config import Settings
from nova_action_engine.main import create_app
from nova_contracts import ContextReplyPayload, ContextRequestPayload, PresentIdentityPayload
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.repository import FakeActionRepository


def _harness_app():  # type: ignore[no-untyped-def]
    return create_app(
        Settings(),
        repository=FakeActionRepository(),
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
    )


def _world_model_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="world-model-engine",
        publishable_subjects=frozenset(),
        subscribable_subjects=frozenset({"world_model.context.request"}),
    )


async def test_get_confidence_returns_the_matching_identitys_confidence(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = _harness_app()
    user_id = uuid4()

    async with app.router.lifespan_context(app):
        received: list[ContextRequestPayload] = []
        serving_bus = _world_model_bus(app)

        async def _serve_context(envelope):  # type: ignore[no-untyped-def]
            payload = ContextRequestPayload.model_validate(envelope.payload)
            received.append(payload)
            return ContextReplyPayload(
                user_id=payload.user_id,
                present_identities=[
                    PresentIdentityPayload(
                        identity_id=user_id, confidence=0.87, modality_summary="face"
                    )
                ],
            )

        await serving_bus.serve(
            "world_model.context.request", _serve_context, source_engine="world-model-engine"
        )

        result = await app.state.identity_port.get_confidence(user_id=user_id)

        assert result == 0.87
        assert len(received) == 1
        assert received[0].user_id == user_id


async def test_get_confidence_returns_none_when_no_matching_identity_is_present(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = _harness_app()

    async with app.router.lifespan_context(app):
        serving_bus = _world_model_bus(app)

        async def _serve_context(envelope):  # type: ignore[no-untyped-def]
            payload = ContextRequestPayload.model_validate(envelope.payload)
            return ContextReplyPayload(user_id=payload.user_id, present_identities=[])

        await serving_bus.serve(
            "world_model.context.request", _serve_context, source_engine="world-model-engine"
        )

        result = await app.state.identity_port.get_confidence(user_id=uuid4())

        assert result is None


async def test_get_confidence_returns_none_when_the_reply_is_degraded(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """ADR-032's fail-closed path: a `degraded` reply (Redis unreachable,
    docs/design/phase-1/03-world-model-engine.md §17) is treated as no
    signal, never a stale/false confidence value."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = _harness_app()
    user_id = uuid4()

    async with app.router.lifespan_context(app):
        serving_bus = _world_model_bus(app)

        async def _serve_context(envelope):  # type: ignore[no-untyped-def]
            payload = ContextRequestPayload.model_validate(envelope.payload)
            return ContextReplyPayload(
                user_id=payload.user_id,
                present_identities=[
                    PresentIdentityPayload(
                        identity_id=user_id, confidence=0.99, modality_summary="face"
                    )
                ],
                degraded=True,
            )

        await serving_bus.serve(
            "world_model.context.request", _serve_context, source_engine="world-model-engine"
        )

        result = await app.state.identity_port.get_confidence(user_id=user_id)

        assert result is None

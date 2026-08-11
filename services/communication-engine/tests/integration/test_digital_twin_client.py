"""`clients.digital_twin_client.DigitalTwinClient` (Phase 2D-D docs/design/
phase-2d/06-personal-companion.md Sec7.2) -- a real Event Bus round trip
through `digital_twin.preferences.get.request`, mirroring
`test_conversation_orchestration.py`'s own
`test_a_real_turn_over_http_reaches_a_real_reasoning_rpc_round_trip`
convention: an in-process stand-in for `digital-twin-engine`'s own network
position *serves* the request for real over the in-memory Event Bus, and
this engine's own (non-fake) `DigitalTwinClient`, constructed by `create_app`
with no override, calls it -- the wire contract itself is exercised, not
bypassed by dependency injection.
"""

from __future__ import annotations

from uuid import uuid4

from nova_communication_engine.config import Settings
from nova_communication_engine.domain.ports import PreferenceSelection
from nova_communication_engine.main import create_app
from nova_contracts import (
    DigitalTwinPreferencesGetReplyPayload,
    DigitalTwinPreferencesGetRequestPayload,
)
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.ports import (
    FakeModelOrchestrationPort,
    FakePersonalityPort,
    FakeReasoningPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeCommunicationRepository


async def test_a_real_get_preferences_call_reaches_a_real_digital_twin_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
        # No digital_twin_port override -- the real `DigitalTwinClient` is
        # constructed by `create_app` and calls the real in-memory bus.
    )

    async with app.router.lifespan_context(app):
        received_requests: list[DigitalTwinPreferencesGetRequestPayload] = []

        digital_twin_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="digital-twin-engine",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"digital_twin.preferences.get.request"}),
        )

        async def _serve_preferences_get(envelope):  # type: ignore[no-untyped-def]
            payload = DigitalTwinPreferencesGetRequestPayload.model_validate(envelope.payload)
            received_requests.append(payload)
            return DigitalTwinPreferencesGetReplyPayload(
                user_id=payload.user_id,
                preferences={"conversation_pacing": "unhurried", "habit_timing_hint": "evenings"},
            )

        await digital_twin_bus.serve(
            "digital_twin.preferences.get.request",
            _serve_preferences_get,
            source_engine="digital-twin-engine",
        )

        user_id = uuid4()
        result = await app.state.digital_twin_port.get_preferences(user_id=user_id)

        assert result == PreferenceSelection(
            conversation_pacing="unhurried", habit_timing_hint="evenings"
        )
        assert len(received_requests) == 1
        assert received_requests[0].user_id == user_id


async def test_no_stored_preferences_yet_returns_none(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """`digital-twin-engine`'s own reply for a brand-new user carries
    `preferences=None` -- `DigitalTwinClient` passes that through as `None`
    rather than an empty `PreferenceSelection`, matching
    `domain.ports.DigitalTwinPort`'s own documented convention."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    app = create_app(
        Settings(),
        repository=FakeCommunicationRepository(),
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
    )

    async with app.router.lifespan_context(app):
        digital_twin_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="digital-twin-engine",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"digital_twin.preferences.get.request"}),
        )

        async def _serve_preferences_get(envelope):  # type: ignore[no-untyped-def]
            payload = DigitalTwinPreferencesGetRequestPayload.model_validate(envelope.payload)
            return DigitalTwinPreferencesGetReplyPayload(user_id=payload.user_id, preferences=None)

        await digital_twin_bus.serve(
            "digital_twin.preferences.get.request",
            _serve_preferences_get,
            source_engine="digital-twin-engine",
        )

        result = await app.state.digital_twin_port.get_preferences(user_id=uuid4())

        assert result is None

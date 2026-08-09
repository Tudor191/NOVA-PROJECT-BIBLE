"""A real Event Bus round-trip through `events/handlers.py::
make_addressee_signal_handler` (docs/design/phase-2d/
04-conversation-intelligence.md Sec4/Sec10/Sec22.2) -- verifies the
subscription registered by `create_app` actually receives a
`perception.addressee_signal.candidate` event and records a
`ConversationDecisionTrace`, using `nova_testkit`'s
`FakePerceptionSignalSource` as the disclosed stand-in for
perception-engine's still-unwired production publisher (TDD Sec0.4, Option
B). This is exactly the "contract-level, fake-driven" tier Sec22.1/Sec22.2
describe -- not an end-to-end proof against real perception-engine
sensors, which Sec0.4/Sec22.4 explicitly name as still open.
"""

from __future__ import annotations

from uuid import uuid4

from nova_communication_engine.config import Settings
from nova_communication_engine.main import create_app
from nova_contracts.events.perception import GazeDirection
from nova_testkit import FakePerceptionSignalSource

from tests.fakes.ports import (
    FakeModelOrchestrationPort,
    FakePersonalityPort,
    FakeReasoningPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeCommunicationRepository


async def test_a_published_candidate_signal_produces_a_recorded_decision_trace(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = create_app(
        Settings(),
        repository=repository,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
    )

    async with app.router.lifespan_context(app):
        source = FakePerceptionSignalSource()
        await source.publish_addressee_signal_candidate(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            user_id=uuid4(),
            wake_word_matched=True,
            wake_word_confidence=1.0,
            gaze_direction=GazeDirection.TOWARD_DEVICE,
            session_active=True,
        )

        assert len(repository.decision_traces) == 1
        trace = repository.decision_traces[0]
        assert trace.decision_type == "addressee_fusion"
        assert trace.session_id is None
        assert trace.outcome == "activated"
        assert trace.confidence_tier == "medium"  # score 0.70 is below the 0.85 "high" tier floor
        assert trace.confidence is not None and trace.confidence >= 0.70


async def test_a_low_confidence_signal_records_a_silent_outcome(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = create_app(
        Settings(),
        repository=repository,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=FakeReasoningPort(),
    )

    async with app.router.lifespan_context(app):
        source = FakePerceptionSignalSource()
        await source.publish_addressee_signal_candidate(
            app.state.bus._bus, user_id=uuid4()
        )  # noqa: SLF001

        assert len(repository.decision_traces) == 1
        trace = repository.decision_traces[0]
        assert trace.outcome == "silent"
        assert trace.confidence == 0.0

"""`conversation_orchestration.handle_conversation_turn` (docs/design/
phase-2d/05-conversation-intelligence-closure.md Sec5, Priority 3) -- the
previously-missing communication-engine <-> reasoning-engine conversation
loop:

    communication.turn.received -> communication-engine -> reasoning-engine
    (reasoning.reason.request) -> reasoning result -> communication-engine
    -> intent gate -> response delivery

Exercised through the real, lifespan-driven FastAPI app (mirrors
`test_events_communication_request.py`'s own convention), against fakes for
every upstream port -- calling `handle_conversation_turn` directly (bypassing
the WebSocket/HTTP layer, which `test_api_sessions.py`/`test_websocket_text.py`
already cover for the turn-recording half) isolates this module's own new
logic: what content/confidence_tier gets chosen from a reasoning outcome, and
that it reaches the same delivery path `communication.intent.deliver.request`
already uses.

`test_a_real_turn_over_http_reaches_a_real_reasoning_rpc_round_trip` is the
strongest proof: an in-process stand-in for reasoning-engine's own network
position *serves* `reasoning.reason.request` for real over the in-memory
Event Bus, and this engine's own (non-fake) `ReasoningClient` calls it --
the wire contract itself is exercised, not bypassed by dependency injection.
"""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient
from nova_communication_engine.config import Settings
from nova_communication_engine.conversation_orchestration import (
    FALLBACK_CONTENT,
    handle_conversation_turn,
    maybe_activate_listening,
)
from nova_communication_engine.domain.models import (
    ChannelType,
    ConversationSession,
    ConversationState,
)
from nova_communication_engine.domain.ports import ReasoningOutcomeResult, ValidationOutcome
from nova_communication_engine.main import create_app
from nova_contracts import ReasoningReplyPayload, ReasoningRequestPayload
from nova_eventbus_sdk import BoundEventBus

from tests.fakes.channel_adapter import FakeChannelAdapter
from tests.fakes.ports import (
    FakeModelOrchestrationPort,
    FakePersonalityPort,
    FakeReasoningPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeCommunicationRepository


def _thinking_session(**overrides: object) -> ConversationSession:
    defaults: dict[str, object] = dict(
        user_id=uuid4(),
        channel=ChannelType.TEXT,
        device_id=uuid4(),
        state=ConversationState.THINKING,
    )
    defaults.update(overrides)
    return ConversationSession(**defaults)  # type: ignore[arg-type]


def _voice_session(**overrides: object) -> ConversationSession:
    defaults: dict[str, object] = dict(
        user_id=uuid4(),
        channel=ChannelType.VOICE,
        device_id=uuid4(),
        state=ConversationState.IDLE,
    )
    defaults.update(overrides)
    return ConversationSession(**defaults)  # type: ignore[arg-type]


def _make_app(
    *,
    repository: FakeCommunicationRepository,
    reasoning_port: FakeReasoningPort,
    personality_port: FakePersonalityPort | None = None,
):
    return create_app(
        Settings(),
        repository=repository,
        personality_port=personality_port or FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=reasoning_port,
    )


async def test_successful_reasoning_result_is_delivered_through_the_intent_gate(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    reasoning_port = FakeReasoningPort(
        result=ReasoningOutcomeResult(
            outcome="decided", content="The build finished.", confidence_score=0.9
        )
    )
    app = _make_app(repository=repository, reasoning_port=reasoning_port)

    async with app.router.lifespan_context(app):
        # Created *after* the lifespan starts -- restart recovery
        # (`main.py`) force-pauses every non-terminal session it finds at
        # startup, which would immediately invalidate this seeded `thinking`
        # state if it existed before the app started.
        session = await repository.create_session(_thinking_session())
        adapter = FakeChannelAdapter()
        app.state.session_registry.register(session.session_id, adapter)

        outcome = await handle_conversation_turn(
            app,
            session_id=session.session_id,
            user_id=session.user_id,
            content="How did the build go?",
            correlation_id=session.session_id,
        )

        assert outcome is not None
        assert outcome.delivered is True
        assert adapter.delivered[0].content == "The build finished."
        assert reasoning_port.reason_calls == [
            ("How did the build go?", session.user_id, session.session_id)
        ]
        updated = await repository.get_session(session.session_id)
        assert updated is not None
        assert updated.state == ConversationState.WAITING


async def test_reasoning_outcome_not_decided_falls_back_to_an_honest_message(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    reasoning_port = FakeReasoningPort(
        result=ReasoningOutcomeResult(outcome="failed", error="pipeline exploded")
    )
    app = _make_app(repository=repository, reasoning_port=reasoning_port)

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_thinking_session())
        adapter = FakeChannelAdapter()
        app.state.session_registry.register(session.session_id, adapter)

        outcome = await handle_conversation_turn(
            app,
            session_id=session.session_id,
            user_id=session.user_id,
            content="Anything to report?",
            correlation_id=session.session_id,
        )

        assert outcome is not None
        assert outcome.delivered is True
        assert adapter.delivered[0].content == FALLBACK_CONTENT


async def test_reasoning_timeout_falls_back_to_an_honest_message(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort(raise_timeout=True))

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_thinking_session())
        adapter = FakeChannelAdapter()
        app.state.session_registry.register(session.session_id, adapter)

        outcome = await handle_conversation_turn(
            app,
            session_id=session.session_id,
            user_id=session.user_id,
            content="Hello?",
            correlation_id=session.session_id,
        )

        assert outcome is not None
        assert outcome.delivered is True
        assert adapter.delivered[0].content == FALLBACK_CONTENT


async def test_a_decided_outcome_with_no_content_is_treated_as_malformed(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    reasoning_port = FakeReasoningPort(
        result=ReasoningOutcomeResult(outcome="decided", content=None, confidence_score=0.9)
    )
    app = _make_app(repository=repository, reasoning_port=reasoning_port)

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_thinking_session())
        adapter = FakeChannelAdapter()
        app.state.session_registry.register(session.session_id, adapter)

        outcome = await handle_conversation_turn(
            app,
            session_id=session.session_id,
            user_id=session.user_id,
            content="Hello?",
            correlation_id=session.session_id,
        )

        assert outcome is not None
        assert adapter.delivered[0].content == FALLBACK_CONTENT


async def test_personality_hard_stop_rejects_delivery(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    reasoning_port = FakeReasoningPort(
        result=ReasoningOutcomeResult(outcome="decided", content="Act now, don't wait.")
    )
    personality_port = FakePersonalityPort(
        outcome=ValidationOutcome(passed=False, rejection_reason="forbidden_pattern: x")
    )
    app = _make_app(
        repository=repository, reasoning_port=reasoning_port, personality_port=personality_port
    )

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_thinking_session())
        adapter = FakeChannelAdapter()
        app.state.session_registry.register(session.session_id, adapter)

        outcome = await handle_conversation_turn(
            app,
            session_id=session.session_id,
            user_id=session.user_id,
            content="What should I do?",
            correlation_id=session.session_id,
        )

        assert outcome is not None
        assert outcome.delivered is False
        assert outcome.rejection_reason == "forbidden_pattern: x"
        assert adapter.delivered == []


async def test_no_live_channel_connection_records_but_does_not_deliver(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_thinking_session())
        # Deliberately never registered in `session_registry` -- no live
        # WebSocket connection, e.g. `send_message`'s own documented
        # "acknowledgment now, answer delivered later" case where nothing
        # is connected yet.
        outcome = await handle_conversation_turn(
            app,
            session_id=session.session_id,
            user_id=session.user_id,
            content="Hello?",
            correlation_id=session.session_id,
        )

        assert outcome is not None
        assert outcome.delivered is False
        assert outcome.rejection_reason == "no_live_channel_connection"


async def test_session_gone_before_delivery_returns_none_without_raising(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        # Never created in the repository -- simulates the session having
        # been closed/removed while this ran in the background.
        outcome = await handle_conversation_turn(
            app,
            session_id=uuid4(),
            user_id=uuid4(),
            content="Hello?",
            correlation_id=uuid4(),
        )

        assert outcome is None


async def test_a_real_turn_over_http_reaches_a_real_reasoning_rpc_round_trip(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The `reasoning-engine` side is a stand-in bus client (this engine has
    no reasoning-engine to run against in this sandbox), but the request it
    serves and the client that calls it (`ReasoningClient`, not a fake) are
    both the real, registered wire contracts -- proving the loop this
    closure exists to build actually reaches `reasoning.reason.request`
    with the turn's own content, not merely that a fake was invoked."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = create_app(
        Settings(),
        repository=repository,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        # No reasoning_port override -- the real `ReasoningClient` is
        # constructed by `create_app` and calls the real in-memory bus.
    )

    async with app.router.lifespan_context(app):
        received_requests: list[ReasoningRequestPayload] = []

        reasoning_bus = BoundEventBus(
            app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
            engine_name="reasoning-engine",
            publishable_subjects=frozenset(),
            subscribable_subjects=frozenset({"reasoning.reason.request"}),
        )

        async def _serve_reason_request(envelope):  # type: ignore[no-untyped-def]
            payload = ReasoningRequestPayload.model_validate(envelope.payload)
            received_requests.append(payload)
            return ReasoningReplyPayload(
                reasoning_process_id=uuid4(),
                decision_id=uuid4(),
                chosen_description="Everything looks good.",
                confidence_score=0.95,
                outcome="decided",
            )

        await reasoning_bus.serve(
            "reasoning.reason.request", _serve_reason_request, source_engine="reasoning-engine"
        )

        created = await repository.create_session(_thinking_session())
        adapter = FakeChannelAdapter()
        app.state.session_registry.register(created.session_id, adapter)

        outcome = await handle_conversation_turn(
            app,
            session_id=created.session_id,
            user_id=created.user_id,
            content="Did the deployment succeed?",
            correlation_id=created.session_id,
        )

        assert outcome is not None
        assert outcome.delivered is True
        assert adapter.delivered[0].content == "Everything looks good."
        assert len(received_requests) == 1
        assert received_requests[0].objective_text == "Did the deployment succeed?"
        assert received_requests[0].user_id == created.user_id
        assert received_requests[0].requesting_engine == "communication-engine"


def test_send_message_over_http_schedules_a_background_turn_that_reaches_delivery(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The production entry point (`schedule_conversation_turn`, reached via
    `POST /sessions/{id}/messages`), not `handle_conversation_turn` called
    directly -- proves the fire-and-forget wiring in `api/sessions.py`
    itself, not just the function it schedules."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    reasoning_port = FakeReasoningPort(
        result=ReasoningOutcomeResult(outcome="decided", content="Right away.")
    )
    app = _make_app(repository=repository, reasoning_port=reasoning_port)

    with TestClient(app) as client:
        created = client.post(
            "/v1/communication/sessions",
            json={"user_id": str(uuid4()), "channel": "text", "device_id": str(uuid4())},
        ).json()
        session_id = created["session_id"]

        with client.websocket_connect(f"/v1/communication/sessions/{session_id}"):
            message = client.post(
                f"/v1/communication/sessions/{session_id}/messages", json={"content": "Hello NOVA"}
            )
            assert message.status_code == 202

            deadline = time.monotonic() + 2.0
            state = None
            while time.monotonic() < deadline:
                state = client.get(f"/v1/communication/sessions/{session_id}/context").json()[
                    "state"
                ]
                if state == "waiting":
                    break
                time.sleep(0.02)
            assert state == "waiting"
        assert reasoning_port.reason_calls[0][0] == "Hello NOVA"


# `maybe_activate_listening` (Phase 2D-C Closure Priority 4, docs/design/
# phase-2d/05-conversation-intelligence-closure.md Sec6; Priority 4 review
# Sec3) -- resolves `user_id` to zero, one, or more eligible sessions
# (connected, voice-channel, Idle/Waiting) and triggers the single
# unambiguous match's `StartListeningSignal`. Exercised through the real
# app + lifespan, calling the function directly (mirrors this file's own
# existing `handle_conversation_turn` tests) rather than through the
# addressee-signal handler -- `test_addressee_signal_handler.py` already
# covers that wiring at the Event Bus tier.


async def test_maybe_activate_listening_triggers_the_single_eligible_connected_session(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_voice_session())
        app.state.session_registry.register(
            session.session_id, FakeChannelAdapter(channel_type="voice")
        )

        await maybe_activate_listening(app, user_id=session.user_id, correlation_id=uuid4())

        signal = app.state.session_registry.get_start_listening_signal(session.session_id)
        assert signal is not None
        assert signal.is_set() is True

        traces = [
            t for t in repository.decision_traces if t.decision_type == "listening_activation"
        ]
        assert len(traces) == 1
        assert traces[0].outcome == "activated"
        assert traces[0].session_id == session.session_id


async def test_maybe_activate_listening_is_a_no_op_with_zero_eligible_sessions(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        # No session exists at all for this user_id.
        await maybe_activate_listening(app, user_id=uuid4(), correlation_id=uuid4())

        traces = [
            t for t in repository.decision_traces if t.decision_type == "listening_activation"
        ]
        assert len(traces) == 1
        assert traces[0].outcome == "no_eligible_session"
        assert traces[0].session_id is None


async def test_maybe_activate_listening_declines_to_guess_with_multiple_eligible_sessions(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        first = await repository.create_session(_voice_session(user_id=user_id))
        second = await repository.create_session(_voice_session(user_id=user_id))
        app.state.session_registry.register(
            first.session_id, FakeChannelAdapter(channel_type="voice")
        )
        app.state.session_registry.register(
            second.session_id, FakeChannelAdapter(channel_type="voice")
        )

        await maybe_activate_listening(app, user_id=user_id, correlation_id=uuid4())

        # Neither candidate is triggered -- a false positive on the wrong
        # device is strictly worse than staying silent (Doc 22 Principle 6).
        for session_id in (first.session_id, second.session_id):
            signal = app.state.session_registry.get_start_listening_signal(session_id)
            assert signal is not None
            assert signal.is_set() is False

        traces = [
            t for t in repository.decision_traces if t.decision_type == "listening_activation"
        ]
        assert len(traces) == 1
        assert traces[0].outcome == "ambiguous_sessions"
        assert traces[0].session_id is None
        candidate_ids = set(traces[0].inputs["candidate_session_ids"])
        assert candidate_ids == {str(first.session_id), str(second.session_id)}


async def test_maybe_activate_listening_ignores_a_session_not_idle_or_waiting(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_voice_session(state=ConversationState.THINKING))
        app.state.session_registry.register(
            session.session_id, FakeChannelAdapter(channel_type="voice")
        )

        await maybe_activate_listening(app, user_id=session.user_id, correlation_id=uuid4())

        signal = app.state.session_registry.get_start_listening_signal(session.session_id)
        assert signal is not None
        assert signal.is_set() is False
        traces = [
            t for t in repository.decision_traces if t.decision_type == "listening_activation"
        ]
        assert traces[0].outcome == "no_eligible_session"


async def test_maybe_activate_listening_ignores_a_disconnected_session(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        session = await repository.create_session(_voice_session())
        # Deliberately never registered in session_registry -- no live
        # WebSocket connection for this session.

        await maybe_activate_listening(app, user_id=session.user_id, correlation_id=uuid4())

        traces = [
            t for t in repository.decision_traces if t.decision_type == "listening_activation"
        ]
        assert traces[0].outcome == "no_eligible_session"


async def test_maybe_activate_listening_ignores_text_channel_sessions(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, reasoning_port=FakeReasoningPort())

    async with app.router.lifespan_context(app):
        session = await repository.create_session(
            _voice_session(channel=ChannelType.TEXT, device_id=uuid4())
        )
        app.state.session_registry.register(
            session.session_id, FakeChannelAdapter(channel_type="text")
        )

        await maybe_activate_listening(app, user_id=session.user_id, correlation_id=uuid4())

        traces = [
            t for t in repository.decision_traces if t.decision_type == "listening_activation"
        ]
        assert traces[0].outcome == "no_eligible_session"

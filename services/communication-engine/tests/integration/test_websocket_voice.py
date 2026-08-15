"""`WS /v1/communication/sessions/{id}` -- voice channel (docs/design/
phase-2d/01-communication-engine.md Sec12; Phase 2D-C Closure Priority 4,
docs/design/phase-2d/05-conversation-intelligence-closure.md Sec6):

- Server-triggered listening activation: a real `perception.
  addressee_signal.candidate` event, published over the app's own in-memory
  Event Bus via `TestClient`'s own portal (so it runs on the same event
  loop/thread as the WebSocket connection it's meant to affect, not a
  second, unsynchronized one), drives audio capture on a connected voice
  session's WebSocket -- *without* the client ever sending `TRIGGER_START`.
  A second test proves the negative: a mismatched `user_id` never triggers.
- The Fork E regression (Priority 4 review Sec1.3): a real barge-in,
  followed by the user's continuing speech, must not crash the connection.

Uses `client.portal` (the `anyio.BlockingPortal` `TestClient.__enter__`
exposes) to run the extra async Event Bus publish on the exact same
loop/thread FastAPI's own lifespan and this WebSocket connection run on --
`nova_eventbus_sdk`'s `InMemoryEventBus` is not loop-bound itself, but the
`repository`/`session_registry` state its subscribed handlers mutate is
plain, non-thread-safe Python state also touched by the connection's own
receive loop, so publishing must not run on an unrelated event loop/thread
(portal.call executes it on the correct one, exactly like every other
request `TestClient` itself issues)."""

from __future__ import annotations

import asyncio
import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from nova_communication_engine.config import Settings
from nova_communication_engine.domain.models import ConversationState
from nova_communication_engine.main import create_app
from nova_contracts.events.perception import GazeDirection
from nova_testkit import FakePerceptionSignalSource, wait_until

from tests.fakes.ports import (
    FakeModelOrchestrationPort,
    FakePersonalityPort,
    FakeReasoningPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeCommunicationRepository

_FAST_VAD_SETTINGS = Settings(communication_engine_vad_end_of_utterance_silence_ms=150.0)
_SILENCE_POLL_INTERVAL_S = 0.1  # mirrors api/websocket.py's own constant


def _wait_for_turn_count(
    client: TestClient, session_id: str, expected: int, *, timeout_s: float = 2.0
) -> dict:
    deadline = time.monotonic() + timeout_s
    context: dict = {}
    while time.monotonic() < deadline:
        context = client.get(f"/v1/communication/sessions/{session_id}/context").json()
        if context["turn_count"] >= expected:
            return context
        time.sleep(0.02)
    return context


def _make_app(*, repository: FakeCommunicationRepository, hold_reasoning: bool = False):
    # `hold_reasoning`: mirrors test_websocket_text.py's own rationale --
    # asserts state/turn_count immediately after the inbound turn is
    # recorded, before Priority 3's background reasoning round trip would
    # otherwise complete and (for a voice channel) synthesize and deliver a
    # second, outbound turn, changing turn_count out from under the
    # assertion.
    reasoning_port = (
        FakeReasoningPort(hold=asyncio.Event()) if hold_reasoning else FakeReasoningPort()
    )
    return create_app(
        _FAST_VAD_SETTINGS,
        repository=repository,
        personality_port=FakePersonalityPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        world_model_port=FakeWorldModelPort(),
        reasoning_port=reasoning_port,
    )


def test_server_triggered_listening_activates_without_a_client_trigger_start(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, hold_reasoning=True)

    with TestClient(app) as client:
        user_id = uuid4()
        created = client.post(
            "/v1/communication/sessions",
            json={"user_id": str(user_id), "channel": "voice", "device_id": str(uuid4())},
        ).json()
        session_id = created["session_id"]
        assert created["state"] == "idle"

        with client.websocket_connect(f"/v1/communication/sessions/{session_id}") as websocket:
            source = FakePerceptionSignalSource()
            assert client.portal is not None
            client.portal.call(
                lambda: source.publish_addressee_signal_candidate(
                    app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
                    user_id=user_id,
                    wake_word_matched=True,
                    wake_word_confidence=1.0,
                    gaze_direction=GazeDirection.TOWARD_DEVICE,
                    session_active=True,
                )
            )

            # Deterministically wait for the receive loop's own silence-poll
            # tick to observe and consume the StartListeningSignal *before*
            # any audio is sent -- otherwise this single AUDIO_CHUNK frame
            # could race ahead of the poll and arrive while `turn_active` is
            # still False (dropped silently, since the receive loop only
            # checks the signal on its own asyncio.wait_for timeout branch,
            # which a successfully-received frame bypasses entirely).
            # `InMemoryEventBus.publish()` awaits every subscriber handler
            # in-line (no `create_task` anywhere in the addressee-signal ->
            # `maybe_activate_listening` -> `StartListeningSignal.trigger()`
            # chain), so the signal is already set by the time portal.call
            # above returns -- the first wait_until below resolves
            # immediately in practice. The second wait_until is what this
            # depends on: it does not resolve until the connection's own
            # receive-loop *task* gets its next scheduler turn and consumes
            # (clears) the signal, which a fixed sleep can only guess at and
            # previously raced under CI's parallel-test CPU contention.
            signal = app.state.session_registry.get_start_listening_signal(UUID(session_id))
            assert signal is not None
            client.portal.call(lambda: wait_until(signal.is_set))
            client.portal.call(lambda: wait_until(lambda: not signal.is_set()))

            websocket.send_bytes(b"\x01" * 32)  # never preceded by a client trigger_start

            context = _wait_for_turn_count(client, session_id, 1)

        assert context["turn_count"] == 1
        assert context["state"] == "thinking"


def test_a_mismatched_user_id_never_accumulates_a_turn(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository)

    with TestClient(app) as client:
        created = client.post(
            "/v1/communication/sessions",
            json={"user_id": str(uuid4()), "channel": "voice", "device_id": str(uuid4())},
        ).json()
        session_id = created["session_id"]

        with client.websocket_connect(f"/v1/communication/sessions/{session_id}") as websocket:
            source = FakePerceptionSignalSource()
            assert client.portal is not None
            client.portal.call(
                lambda: source.publish_addressee_signal_candidate(
                    app.state.bus._bus,  # noqa: SLF001
                    user_id=uuid4(),  # deliberately does not match the session's own user_id
                    wake_word_matched=True,
                    wake_word_confidence=1.0,
                    gaze_direction=GazeDirection.TOWARD_DEVICE,
                    session_active=True,
                )
            )
            time.sleep(_SILENCE_POLL_INTERVAL_S * 3)
            websocket.send_bytes(b"\x01" * 32)
            # No poll-until-true is possible for a negative -- wait out a
            # window comfortably longer than end-of-utterance silence would
            # need, then assert the turn never materialized.
            time.sleep(0.5)

        context = client.get(f"/v1/communication/sessions/{session_id}/context").json()
        assert context["turn_count"] == 0
        # Disconnect (the `with` block above exiting) always pauses a
        # non-completed session regardless of prior state (api/websocket.py's
        # own documented behavior) -- "idle" was never a reachable
        # post-disconnect state here; the turn_count assertion above is this
        # test's actual claim.
        assert context["state"] == "paused"


def test_a_barge_in_followed_by_continuing_speech_does_not_crash_the_connection(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Fork E regression (Priority 4 review Sec1.3): before the fix,
    `record_inbound_turn` unconditionally applied `TRIGGER`, which is not a
    defined edge from `Listening` -- the state a barge-in leaves the session
    in -- raising `InvalidTransitionError` uncaught anywhere in
    `api/websocket.py`'s receive loop and crashing the connection on the
    very first utterance following any barge-in. Forces the session
    directly to `Speaking` (bypassing the full reasoning/delivery pipeline,
    irrelevant to this specific defect) to drive a real barge-in through the
    actual WebSocket loop without needing a synthesized first response --
    the same direct-repository-seeding technique
    `test_conversation_orchestration.py` already uses to set up a
    precondition state, applied here to a live, connected session rather
    than at creation time."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCommunicationRepository()
    app = _make_app(repository=repository, hold_reasoning=True)

    with TestClient(app) as client:
        created = client.post(
            "/v1/communication/sessions",
            json={"user_id": str(uuid4()), "channel": "voice", "device_id": str(uuid4())},
        ).json()
        session_id = created["session_id"]
        session_uuid = UUID(session_id)

        with client.websocket_connect(f"/v1/communication/sessions/{session_id}") as websocket:
            repository.sessions[session_uuid] = repository.sessions[session_uuid].model_copy(
                update={"state": ConversationState.SPEAKING}
            )

            # One AUDIO_CHUNK frame while (forced) Speaking: the receive
            # loop's own barge-in branch fires unconditionally (design doc
            # Sec4), moving the session Speaking -> Listening and setting
            # turn_active -- then, since turn_active is now true, this same
            # frame's audio is also fed into the just-reset VAD as the start
            # of the continuing utterance.
            websocket.send_bytes(b"\x01" * 32)

            context = _wait_for_turn_count(client, session_id, 1)

        assert context["turn_count"] == 1
        assert context["state"] == "thinking"

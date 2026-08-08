"""Verifies `FakePerceptionSignalSource` (`perception_signal_source.py`)
publishes real, correctly-shaped `perception.*` events onto the `event_bus`
fixture -- no network, no testcontainers, no engine import (nova-testkit's
own tests stay as dependency-clean as its `src/`, per ADR-033; the "does a
real consuming engine's own subscription handler work against this fake"
proof lives in that engine's own test suite instead, e.g.
communication-engine's addressee-fusion tests).
"""

from uuid import uuid4

from nova_contracts import EventEnvelope, PerceptionAddresseeSignalCandidatePayload
from nova_contracts.events.perception import GazeDirection
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_testkit import FakePerceptionSignalSource


async def test_publish_addressee_signal_candidate_reaches_a_subscriber(
    event_bus: InMemoryEventBus, fake_perception_signal_source: FakePerceptionSignalSource
) -> None:
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    await event_bus.subscribe("perception.addressee_signal.candidate", handler)

    identity_id = uuid4()
    await fake_perception_signal_source.publish_addressee_signal_candidate(
        event_bus,
        wake_word_matched=True,
        wake_word_confidence=0.92,
        identity_id=identity_id,
        identity_confidence=0.88,
        gaze_direction=GazeDirection.TOWARD_DEVICE,
        session_active=True,
    )

    assert len(received) == 1
    payload = PerceptionAddresseeSignalCandidatePayload.model_validate(received[0].payload)
    assert payload.wake_word_matched is True
    assert payload.wake_word_confidence == 0.92
    assert payload.identity_id == identity_id
    assert payload.gaze_direction == GazeDirection.TOWARD_DEVICE
    assert payload.session_active is True
    assert payload.schema_version == 1


async def test_defaults_score_low_under_the_documented_fusion_weighting(
    event_bus: InMemoryEventBus, fake_perception_signal_source: FakePerceptionSignalSource
) -> None:
    envelope = await fake_perception_signal_source.publish_addressee_signal_candidate(event_bus)
    payload = PerceptionAddresseeSignalCandidatePayload.model_validate(envelope.payload)

    assert payload.wake_word_matched is False
    assert payload.identity_id is None
    assert payload.gaze_direction == GazeDirection.UNKNOWN
    assert payload.session_active is False


async def test_published_envelopes_are_recorded_in_order(
    event_bus: InMemoryEventBus, fake_perception_signal_source: FakePerceptionSignalSource
) -> None:
    await fake_perception_signal_source.publish_presence_observed(
        event_bus, user_id=uuid4(), present=True
    )
    await fake_perception_signal_source.publish_identity_observed(event_bus, user_id=uuid4())

    assert [e.subject for e in fake_perception_signal_source.published] == [
        "perception.presence.observed",
        "perception.identity.observed",
    ]

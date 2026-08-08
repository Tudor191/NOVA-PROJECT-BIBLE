"""`FakePerceptionSignalSource` -- a deterministic publisher of
`perception.*` events standing in for `perception-engine`'s production
sensor-to-publish chain, which is not yet wired end-to-end
(docs/design/phase-2d/04-conversation-intelligence.md §0.4 -- Phase 2D-B's
`domain/identity_fusion.py` and `sensors/` are real, but nothing in that
engine's production code currently calls
`events/publishers.py::addressee_signal_candidate` outside its own unit
test). Phase 2D-C's addressee-detection fusion (04-conversation-intelligence.md
§4) is built and verified against the *contract* `perception-engine`
already publishes correctly-shaped signals under, per the explicitly
approved Option B (§0.4): this fake is that contract's deterministic,
scripted test double, the same role `FakeModelGateway` plays for
`ai-model-orchestration-engine`.

Deliberately **not** a served-RPC fake like `FakeModelGateway` --
`perception.addressee_signal.candidate` and its five sibling subjects are
publish/subscribe events, not request/reply RPCs (`perception-engine`
serves no RPC of its own, by design -- 03-perception-engine.md §13.1). This
publishes directly onto whatever raw `EventBus` it is given, exactly as a
real engine's outbox dispatcher (`nova_service_kit.outbox`) would after
`events/publishers.py` shapes a payload -- no `BoundEventBus` allow-list
wrapping, since this fake plays the role of an external publisher
(`perception-engine`), not the engine under test.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import (
    EventEnvelope,
    PerceptionAddresseeSignalCandidatePayload,
    PerceptionIdentityObservedPayload,
    PerceptionPresenceObservedPayload,
)
from nova_contracts.events.perception import ConfidenceTier, GazeDirection, PerceptionSource
from nova_eventbus_sdk import EventBus

__all__ = ["FakePerceptionSignalSource"]

_FAKE_SOURCE_ENGINE = "nova-testkit-fake-perception-signal-source"


class FakePerceptionSignalSource:
    """Publishes deterministic, scripted `perception.*` events onto a test's
    `EventBus` -- exercises a consumer's subscription/parsing/fusion logic
    exactly as a real `perception-engine` production publish would, without
    requiring that engine's still-unwired sensor chain to exist.

    Usage: `await source.publish_addressee_signal_candidate(event_bus,
    wake_word_matched=True, ...)`, then assert on whatever the code under
    test (e.g. `communication-engine`'s addressee-fusion subscription
    handler) did in response. `source.published` records every envelope
    published, in order, for call-count/ordering assertions.
    """

    def __init__(self, *, source_engine: str = _FAKE_SOURCE_ENGINE) -> None:
        self.source_engine = source_engine
        self.published: list[EventEnvelope] = []

    async def _publish(
        self, bus: EventBus, *, subject: str, payload_dict: dict[str, object], correlation_id: UUID
    ) -> EventEnvelope:
        envelope = EventEnvelope(
            subject=subject,
            source_engine=self.source_engine,
            correlation_id=correlation_id,
            payload=payload_dict,
        )
        await bus.publish(envelope)
        self.published.append(envelope)
        return envelope

    async def publish_addressee_signal_candidate(
        self,
        bus: EventBus,
        *,
        wake_word_matched: bool = False,
        wake_word_confidence: float = 0.0,
        identity_id: UUID | None = None,
        identity_confidence: float = 0.0,
        gaze_direction: GazeDirection = GazeDirection.UNKNOWN,
        session_active: bool = False,
        correlation_id: UUID | None = None,
    ) -> EventEnvelope:
        """The one subject Phase 2D-C's fusion (04-conversation-intelligence.md
        §4) actually consumes -- every default here scores `LOW` under that
        document's weighting, so a test must opt in to whichever signals it
        wants to exercise a `HIGH`/`UNCERTAIN` outcome."""
        payload = PerceptionAddresseeSignalCandidatePayload(
            wake_word_matched=wake_word_matched,
            wake_word_confidence=wake_word_confidence,
            identity_id=identity_id,
            identity_confidence=identity_confidence,
            gaze_direction=gaze_direction,
            session_active=session_active,
        )
        return await self._publish(
            bus,
            subject="perception.addressee_signal.candidate",
            payload_dict=payload.model_dump(mode="json"),
            correlation_id=correlation_id or uuid4(),
        )

    async def publish_identity_observed(
        self,
        bus: EventBus,
        *,
        user_id: UUID,
        identity_id: UUID | None = None,
        confidence: float = 0.9,
        confidence_tier: ConfidenceTier = ConfidenceTier.HIGH,
        modality_summary: str = "voice+face",
        correlation_id: UUID | None = None,
    ) -> EventEnvelope:
        """World Model's corroborating signal path (04-conversation-intelligence.md
        §4) -- matches World Model's own `perception.*.observed` wildcard
        subscription, so publishing this also exercises
        `world-model-engine`'s `upsert_present_identity` handler if that
        engine's own subscription is wired to the same bus."""
        payload = PerceptionIdentityObservedPayload(
            user_id=user_id,
            identity_id=identity_id,
            confidence=confidence,
            confidence_tier=confidence_tier,
            modality_summary=modality_summary,
        )
        return await self._publish(
            bus,
            subject="perception.identity.observed",
            payload_dict=payload.model_dump(mode="json"),
            correlation_id=correlation_id or uuid4(),
        )

    async def publish_presence_observed(
        self,
        bus: EventBus,
        *,
        user_id: UUID | None,
        present: bool,
        confidence: float = 0.9,
        source: PerceptionSource = PerceptionSource.MICROPHONE,
        correlation_id: UUID | None = None,
    ) -> EventEnvelope:
        payload = PerceptionPresenceObservedPayload(
            user_id=user_id, present=present, confidence=confidence, source=source
        )
        return await self._publish(
            bus,
            subject="perception.presence.observed",
            payload_dict=payload.model_dump(mode="json"),
            correlation_id=correlation_id or uuid4(),
        )

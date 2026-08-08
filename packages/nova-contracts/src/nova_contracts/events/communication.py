"""Communication Engine event payloads (Bible Part 13), per
docs/design/phase-2d/01-communication-engine.md Sec7 (the `communication.
intent` gate), Sec10 (data model), and Sec11 (event contracts); extended by
docs/design/phase-2d/04-conversation-intelligence.md Sec10 for Phase 2D-C's
`ResponseShapingDirectivePayload` and `memory_annotations`.

Every payload carries `schema_version: int = 1` from its first commit
(ADR-024), the same discipline every engine's payloads follow since Phase 2A.

`CommunicationStyle` is imported from `nova_contracts.events.personality`
rather than redefined here -- Bible Part 13's own nine-style palette is
`personality-engine`'s vocabulary (`personality.style.select`'s reply
already returns it); `ResponseShapingDirectivePayload` carries the resolved
value that RPC produced, not a second, independent enum for the same
concept.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from nova_contracts.events.personality import CommunicationStyle
from nova_contracts.registry import register_payload


class ConversationState(StrEnum):
    """Bible Part 13's ten conversation states (design doc Sec3.1).
    `EXECUTING`/`MONITORING`/`LEARNING` are reserved -- no Phase 2D-A
    transition produces them (Phase 3/2D-D do)."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    LEARNING = "learning"


class ChannelType(StrEnum):
    """Design doc Sec3.2, Sec5 -- extensible; exactly two ship this phase."""

    TEXT = "text"
    VOICE = "voice"


class TurnDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class NotificationPriority(StrEnum):
    """Design doc Sec10 -- a minimal enum this phase; Bible Part 13's full
    prioritization intelligence is future scope."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# --- communication.intent.deliver -- the ADR-005 gate (Sec7) ----------------


@register_payload("communication.intent.deliver.request")
class CommunicationIntentDeliverRequestPayload(BaseModel):
    """Every candidate outbound utterance, from any content-source engine
    (Sec8.2), arrives as this request. `confidence_tier` is forwarded
    verbatim to `personality.validate_response` (epistemic deference,
    ADR-028's pattern)."""

    session_id: UUID
    content: str
    confidence_tier: str = "unknown"
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    memory_annotations: list[dict[str, str]] | None = None
    """Phase 2D-C addition (04-conversation-intelligence.md Sec9) -- a
    content-source engine may optionally categorize a piece of its own
    content as one of Bible Part 13's Conversation Memory categories
    (`{"category": "decision" | "preference" | "correction" | "feedback",
    "text": ...}`). `communication-engine` only stores what it's told,
    categorized by the producing engine -- it never infers or extracts a
    category itself (Sec0.1: this engine never generates or classifies
    content, only transports and gates it). `None`/absent is the common
    case and changes nothing about delivery."""
    schema_version: int = 1


@register_payload("communication.intent.deliver.reply")
class CommunicationIntentDeliverReplyPayload(BaseModel):
    """`delivered=False` covers two distinct causes, distinguished by
    `rejection_reason`: a personality hard-stop (content must never reach
    the user, design doc Sec7 step 2 / 02-personality-engine.md Sec8) versus
    a channel/session-level delivery failure (design doc Sec9)."""

    delivered: bool
    personality_validated: bool
    degraded: bool = False
    turn_id: UUID | None = None
    rejection_reason: str | None = None
    schema_version: int = 1


# --- communication.session.create --------------------------------------------


@register_payload("communication.session.create.request")
class CommunicationSessionCreateRequestPayload(BaseModel):
    user_id: UUID
    channel: ChannelType
    device_id: UUID
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1


@register_payload("communication.session.create.reply")
class CommunicationSessionCreateReplyPayload(BaseModel):
    session_id: UUID
    state: ConversationState
    created_at: datetime
    schema_version: int = 1


# --- communication.session.close ---------------------------------------------


@register_payload("communication.session.close.request")
class CommunicationSessionCloseRequestPayload(BaseModel):
    session_id: UUID
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1


@register_payload("communication.session.close.reply")
class CommunicationSessionCloseReplyPayload(BaseModel):
    session_id: UUID
    state: ConversationState
    closed_at: datetime
    schema_version: int = 1


# --- Published events (Sec11) -------------------------------------------------


@register_payload("communication.session.created")
class CommunicationSessionCreatedPayload(BaseModel):
    session_id: UUID
    user_id: UUID
    channel: ChannelType
    device_id: UUID
    created_at: datetime
    schema_version: int = 1


@register_payload("communication.session.state_changed")
class CommunicationSessionStateChangedPayload(BaseModel):
    """Design doc Sec3.1, Sec11 -- the Live Communication Dashboard's data
    source: the real current state, never an approximation."""

    session_id: UUID
    from_state: ConversationState
    to_state: ConversationState
    changed_at: datetime
    schema_version: int = 1


@register_payload("communication.session.completed")
class CommunicationSessionCompletedPayload(BaseModel):
    """Design doc Sec8.6 -- the only long-term retention of conversation
    content; Memory Engine is this event's intended (not yet wired,
    out of Phase 2D-A scope) subscriber."""

    session_id: UUID
    user_id: UUID
    objective: str | None = None
    turn_count: int
    closed_at: datetime
    schema_version: int = 1


@register_payload("communication.turn.received")
class CommunicationTurnReceivedPayload(BaseModel):
    """Design doc Sec6's "Determine Intent" pass-through -- published for
    Reasoning Engine (or any future content-source engine) to subscribe to;
    this engine forms no judgment about what the turn means."""

    session_id: UUID
    turn_id: UUID
    user_id: UUID
    content: str
    channel: ChannelType
    created_at: datetime
    schema_version: int = 1


@register_payload("communication.response_shaping.directive")
class ResponseShapingDirectivePayload(BaseModel):
    """Phase 2D-C addition (04-conversation-intelligence.md Sec0.7/Sec7/
    Sec8/Sec10) -- published alongside (same `correlation_id` as)
    `communication.turn.received`, never merged into that payload: this is
    a policy decision *about* the turn, not a property *of* it (the same
    "decision-trace-shaped data gets its own payload" convention
    `ArbitrationResult` already established relative to
    `ExecutiveRequestPayload` in Phase 2C). `communication-engine` computes
    and publishes this; it does not itself apply it to any generated
    content (Sec0.1 -- this engine never generates content). Whether/how a
    content-source engine (e.g. Reasoning Engine) currently consumes it is
    explicitly *not* implied by this payload's existence -- see Sec0.7's
    own disclosed finding that no such consumer exists yet."""

    session_id: UUID
    style: CommunicationStyle
    verbosity: str
    technical_depth: str
    situation_hint: str | None = None
    response_language: str = "en"
    """Doc 22 Principles 10-11 -- English-first this phase; not a per-message
    inference (Principle 9's consistency requirement)."""
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1


# --- Deferred, forward-declared only (design doc Sec0.6) ---------------------


@register_payload("digital_twin.preferences.get.request")
class DigitalTwinPreferencesGetRequestPayload(BaseModel):
    """Design doc Sec0.6 -- defined now per ADR-024 versioning discipline;
    no Phase 2D-A code path calls it. Real integration arrives in Phase
    2D-C, once `digital-twin-engine` (Phase 2D-D) exists."""

    user_id: UUID
    schema_version: int = 1


@register_payload("digital_twin.preferences.get.reply")
class DigitalTwinPreferencesGetReplyPayload(BaseModel):
    user_id: UUID
    preferences: dict[str, Any] | None = None
    schema_version: int = 1

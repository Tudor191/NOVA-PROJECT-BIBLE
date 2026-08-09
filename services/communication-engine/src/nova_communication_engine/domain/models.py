"""Domain entities -- not ORM models (docs/design/phase-2d/
01-communication-engine.md Sec1, Sec3, Sec5, Sec10).

`ConversationState`, `ChannelType`, `TurnDirection`, and `NotificationPriority`
are re-exported from `nova_contracts.events.communication` rather than
redefined here -- executive-cognition-engine's own precedent
(`domain/models.py`'s docstring there) for cross-cutting classification
schemes and wire-identical structural types: `nova_contracts` is a shared
package, not another engine's internals, so importing from it does not cross
ADR-004's boundary.

**The boundary this file exists to enforce** (design doc Sec0.1-Sec0.2): every
model here describes transport and lifecycle state this engine itself owns
(a session, a turn, a channel-neutral message). Nothing here holds generated
content's *meaning* or a copy of another engine's domain conclusion -- this
engine transports and gates content, it never interprets or produces it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from nova_contracts.events.communication import (
    ChannelType,
    ConversationState,
    NotificationPriority,
    TurnDirection,
)
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ChannelCapabilities",
    "ChannelType",
    "ConversationDecisionTrace",
    "ConversationMemory",
    "ConversationSession",
    "ConversationState",
    "ConversationTurn",
    "InboundMessage",
    "InboundMessageKind",
    "Notification",
    "NotificationPriority",
    "OutboundMessage",
    "OutboundMessageKind",
    "TurnDirection",
]

_AUDIO_BYTES_CONFIG = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")
"""Pydantic v2's default `bytes` JSON serialization requires valid UTF-8 and
raises on arbitrary binary -- the same bug found and fixed in
`ai-model-orchestration-engine`'s speech extension (design doc Sec0.3),
applied here for the same reason: `InboundMessage.audio`/`OutboundMessage.
audio` carry real audio bytes."""


class InboundMessageKind(StrEnum):
    """Design doc Sec0.4, Sec5 -- the explicit-trigger interim mechanism:
    `TRIGGER_START`/`TRIGGER_STOP` are the voice channel's push-to-talk-style
    signal, never acoustic wake-word detection."""

    TEXT = "text"
    AUDIO_CHUNK = "audio_chunk"
    TRIGGER_START = "trigger_start"
    TRIGGER_STOP = "trigger_stop"


class OutboundMessageKind(StrEnum):
    TEXT = "text"
    AUDIO_CHUNK = "audio_chunk"


class InboundMessage(BaseModel):
    """Channel-neutral message shape a `ChannelAdapter.receive()` call
    produces (design doc Sec5). `audio` is transient only -- never persisted
    (Sec3.3, Sec15); only its transcript ever reaches a `ConversationTurn`."""

    model_config = _AUDIO_BYTES_CONFIG

    kind: InboundMessageKind
    content: str | None = None
    audio: bytes | None = None


class OutboundMessage(BaseModel):
    """Channel-neutral message shape a `ChannelAdapter.deliver()` call
    consumes (design doc Sec5)."""

    model_config = _AUDIO_BYTES_CONFIG

    kind: OutboundMessageKind
    content: str | None = None
    audio: bytes | None = None


class ChannelCapabilities(BaseModel):
    """Design doc Sec5's `ChannelAdapter.capabilities()` return shape."""

    streaming: bool
    audio: bool
    text: bool


class ConversationTurn(BaseModel):
    """Design doc Sec3.3 -- one row per user input or NOVA output. `content`
    is always present, even for voice turns (the transcript, never only
    audio) -- raw audio is never persisted (Sec15)."""

    turn_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    direction: TurnDirection
    content: str
    channel: ChannelType
    personality_validated: bool | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationMemory(BaseModel):
    """Bible Part 13's Conversation Memory list, minus `objective` (already
    its own top-level `ConversationSession` field, Sec3.2 of the 2D-A design
    doc) -- 04-conversation-intelligence.md Sec0.8/Sec3.1/Sec9. Extends the
    existing durable `ConversationSession` record rather than a new Redis
    store: per Sec0.8, this data must survive a restart exactly as the rest
    of the session does, so it is not treated as ADR-012's ephemeral,
    cheap-to-rebuild category. `decisions`/`preferences`/`corrections`/
    `feedback` are populated only from `memory_annotations` a content-source
    engine optionally sets on its own `communication.intent.deliver.request`
    calls (Sec9) -- this engine stores what it's told, categorized by the
    producing engine, never infers or extracts a category itself."""

    questions: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)


class ConversationSession(BaseModel):
    """Design doc Sec3.2's required fields. `device_id` is present from day
    one even though only one device is ever populated this phase (Master
    Blueprint Risk Sec11.6). `conversation_memory`/`interrupted_content`/
    `dnd_override` are additive, Phase 2D-C fields
    (04-conversation-intelligence.md Sec3.1)."""

    session_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    channel: ChannelType
    device_id: UUID
    state: ConversationState = ConversationState.IDLE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    turns: list[ConversationTurn] = Field(default_factory=list)
    objective: str | None = None
    pending_questions: list[str] | None = None
    """Populated by 2D-C's Clarification Engine (`domain/clarification.py`)."""
    closed_at: datetime | None = None
    conversation_memory: ConversationMemory = Field(default_factory=ConversationMemory)
    interrupted_content: str | None = None
    """Set when a barge-in (2D-A, mechanical) discards in-flight content;
    cleared once resumed or explicitly dropped (Sec5.1) -- "no information
    should be lost" (Bible Part 13's Interruption Management)."""
    dnd_override: bool = False
    """User-set do-not-disturb toggle (Sec5.2) -- the one activity signal
    this phase has without desktop/activity sensing (Phase 4)."""


class ConversationDecisionTrace(BaseModel):
    """One row per addressee-fusion, interruption-recovery, or silence
    decision (04-conversation-intelligence.md Sec3.2, Sec15) -- the
    observability/explainability mechanism, modeled directly on Phase 2C's
    `ExecutiveDecisionTrace` precedent: structured metadata *about* a
    decision, never the content decided about. Append-only, never mutated."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID | None = None
    """`None` for a pre-session addressee check (no session exists yet to
    attach to until/unless the fusion outcome is `HIGH`)."""
    decision_type: Literal[
        "addressee_fusion", "interruption_recovery", "silence", "listening_activation"
    ]
    inputs: dict[str, Any]
    confidence: float | None = None
    confidence_tier: Literal["high", "medium", "low", "unknown"] | None = None
    outcome: str
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = 1


class Notification(BaseModel):
    """Design doc Sec10 -- a minimal record this phase; no delivery-channel
    integration exists yet (design doc Sec12's honest scope note)."""

    notification_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    content: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    delivered_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

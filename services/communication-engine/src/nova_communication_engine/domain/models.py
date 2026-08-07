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


class ConversationSession(BaseModel):
    """Design doc Sec3.2's required fields. `device_id` is present from day
    one even though only one device is ever populated this phase (Master
    Blueprint Risk Sec11.6)."""

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
    """Populated by 2D-C's Clarification Engine -- schema present, unused
    this phase (design doc Sec3.2)."""
    closed_at: datetime | None = None


class Notification(BaseModel):
    """Design doc Sec10 -- a minimal record this phase; no delivery-channel
    integration exists yet (design doc Sec12's honest scope note)."""

    notification_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    content: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    delivered_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

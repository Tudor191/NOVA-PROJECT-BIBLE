"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2d/01-communication-engine.md Sec1, Sec5). `domain/` may
only import this module, `domain/models.py`, and other `domain/` modules --
never FastAPI, SQLAlchemy, `nova_eventbus_sdk`, or (per ADR-020) any LLM/AI
provider SDK directly. No `DigitalTwinPort`/`PerceptionPort` exists this
phase (design doc Sec0.6) -- their wire contracts are forward-declared in
`nova-contracts` for future use, but nothing here calls them yet, so no
Python port exists to abstract a call this document's own runtime never
makes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_communication_engine.domain.models import (
    ChannelCapabilities,
    ConversationSession,
    ConversationTurn,
    InboundMessage,
    Notification,
    OutboundMessage,
)

__all__ = [
    "ChannelAdapter",
    "CommunicationRepository",
    "EventPublisher",
    "ModelOrchestrationPort",
    "OutboxEvent",
    "OutboxRow",
    "PersonalityPort",
    "StyleSelection",
    "ValidationOutcome",
    "WorldModelPort",
    "WorldModelSnapshot",
]


@runtime_checkable
class ChannelAdapter(Protocol):
    """Design doc Sec5 -- one per channel (`TextChannelAdapter`,
    `VoiceChannelAdapter`). Design doc Sec7: only the `communication.intent`
    gate holds a reference to a `ChannelAdapter` instance -- no other code
    path may call `deliver` directly."""

    channel_type: str  # "text" | "voice"

    async def receive(self) -> InboundMessage: ...

    async def deliver(self, message: OutboundMessage) -> None: ...

    def capabilities(self) -> ChannelCapabilities: ...


class ValidationOutcome(BaseModel):
    """Design doc Sec7 step 2 -- the intent gate's own view of a
    `personality.validate_response` result, independent of
    `personality-engine`'s wire schema."""

    passed: bool
    adjusted_content: str | None = None
    rejection_reason: str | None = None


class StyleSelection(BaseModel):
    style: str
    verbosity: str
    technical_depth: str


@runtime_checkable
class PersonalityPort(Protocol):
    """Design doc Sec0.5, Sec8.3 -- a real, load-bearing synchronous
    dependency of the intent gate from day one, unlike every other upstream
    port this engine defines. Implemented by
    `clients/personality_client.py`, calling
    `personality.validate_response.request`/`personality.style.select.
    request`."""

    async def validate_response(
        self,
        *,
        content: str,
        confidence_tier: str,
        session_id: UUID,
        correlation_id: UUID | None = None,
    ) -> ValidationOutcome: ...

    async def select_style(
        self,
        *,
        situation_hint: str | None,
        channel: str | None,
        correlation_id: UUID | None = None,
    ) -> StyleSelection: ...


@runtime_checkable
class ModelOrchestrationPort(Protocol):
    """Design doc Sec0.3, Sec8.1 -- `transcribe`/`synthesize` as served
    Event-Bus RPCs (never a Whisper/Piper SDK directly, ADR-020).
    A `None` result means the Model Router's fallback chain was exhausted
    (design doc Sec9) -- not an exception, so callers apply Sec9's
    documented degraded-mode behavior rather than crash."""

    async def transcribe(
        self, *, audio: bytes, correlation_id: UUID | None = None
    ) -> str | None: ...

    async def synthesize(
        self, *, text: str, correlation_id: UUID | None = None
    ) -> bytes | None: ...


class WorldModelSnapshot(BaseModel):
    user_id: UUID
    objective: str | None = None
    project_id: UUID | None = None
    device: str | None = None
    degraded: bool = False


@runtime_checkable
class WorldModelPort(Protocol):
    """Design doc Sec8.7 -- one context call per session creation, the same
    already-built, sub-20ms p95 `world_model.context.request` RPC every
    other engine already calls. Implemented by
    `clients/world_model_client.py`."""

    async def get_context(
        self, *, user_id: UUID, scope: str | None = None, correlation_id: UUID | None = None
    ) -> WorldModelSnapshot | None: ...


class OutboxEvent(BaseModel):
    """One row to insert into `communication.outbox_event` in the same
    transaction as the write it accompanies -- the same transactional
    outbox pattern every prior engine's own repository uses."""

    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class OutboxRow(BaseModel):
    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime


@runtime_checkable
class CommunicationRepository(Protocol):
    """Persistence port for the `communication` schema (design doc Sec10):
    `conversation_session`, `conversation_turn`, `notification`, and the
    transactional outbox."""

    async def create_session(self, session: ConversationSession) -> ConversationSession: ...

    async def get_session(self, session_id: UUID) -> ConversationSession | None: ...

    async def update_session_state(
        self,
        session_id: UUID,
        *,
        state: str,
        closed_at: datetime | None = None,
        outbox_event: OutboxEvent | None = None,
    ) -> ConversationSession:
        """Synchronous, one write per transition (design doc Sec3.5) -- never
        batched."""
        ...

    async def append_turn(
        self, turn: ConversationTurn, *, outbox_event: OutboxEvent | None = None
    ) -> ConversationTurn: ...

    async def list_non_terminal_sessions(self) -> list[ConversationSession]:
        """Design doc Sec3.5 -- restart recovery's own query: every session
        not in `Completed`, scanned once at startup."""
        ...

    async def create_notification(self, notification: Notification) -> Notification: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Declared for symmetry with every other engine's `domain/ports.py`
    (executive-cognition-engine's own precedent) -- unused by `domain/`
    itself; every outbound RPC this engine makes is reached through one of
    the typed ports above."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...

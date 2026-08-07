"""Protocols this package depends on -- implements nothing itself
(docs/design/phase-2d/03-perception-engine.md Sec1). `domain/` may only
import this module, `domain/models.py`, `domain/sensor.py`, and other
`domain/` modules -- never FastAPI, SQLAlchemy, `nova_eventbus_sdk`, a
camera/audio capture library, or (per ADR-020) any LLM/AI provider SDK
directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from nova_contracts import EventEnvelope
from pydantic import BaseModel

from nova_perception_engine.domain.models import (
    ConsentGrant,
    EnrolledIdentity,
    IdentityObservation,
    Modality,
    Source,
)

__all__ = [
    "AIModelOrchestrationPort",
    "EventPublisher",
    "FaceEmbedResult",
    "GazeEstimateResult",
    "OutboxEvent",
    "OutboxRow",
    "PerceptionRepository",
    "VoiceEmbedResult",
    "WakePhraseResult",
]


class WakePhraseResult(BaseModel):
    """This engine's own view of `ai_model.detect_wake_phrase`'s reply
    (docs/design/phase-2d/03-perception-engine.md Sec0.2) -- independent of
    `ai-model-orchestration-engine`'s wire schema."""

    matched: bool
    confidence: float


class VoiceEmbedResult(BaseModel):
    embedding: list[float]
    confidence: float


class FaceEmbedResult(BaseModel):
    embedding: list[float]
    confidence: float


class GazeEstimateResult(BaseModel):
    gaze_direction: str  # "toward_device" | "away" | "unknown"
    confidence: float


@runtime_checkable
class AIModelOrchestrationPort(Protocol):
    """Sec0.2 -- the sole legal path (ADR-020) to a wake-phrase/voiceprint/
    faceprint/gaze-estimation model. Implemented by
    `clients/ai_model_orchestration_client.py`, calling
    `ai_model.detect_wake_phrase.request`/`ai_model.embed_voice.request`/
    `ai_model.embed_face.request`/`ai_model.estimate_gaze.request`. A `None`
    result means the Model Router's fallback chain was exhausted (Sec12) --
    never an exception, so callers apply Sec12's documented degraded-mode
    behavior (the signal is simply absent from that correlation window)
    rather than crash."""

    async def detect_wake_phrase(
        self, *, audio: bytes, wake_phrase: str | None, correlation_id: UUID | None = None
    ) -> WakePhraseResult | None: ...

    async def embed_voice(
        self, *, audio: bytes, correlation_id: UUID | None = None
    ) -> VoiceEmbedResult | None: ...

    async def embed_face(
        self, *, image: bytes, correlation_id: UUID | None = None
    ) -> FaceEmbedResult | None: ...

    async def estimate_gaze(
        self, *, image: bytes, correlation_id: UUID | None = None
    ) -> GazeEstimateResult | None: ...


class OutboxEvent(BaseModel):
    """One row to insert into `perception.outbox_event` in the same
    transaction as the write it accompanies -- the same transactional outbox
    pattern every prior engine's own repository uses."""

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
class PerceptionRepository(Protocol):
    """Persistence port for the `perception` schema (Sec15):
    `enrolled_identity`, `consent_grant`, `identity_observation`,
    `sensor_registration`, and the transactional outbox."""

    async def enroll_identity(self, identity: EnrolledIdentity) -> EnrolledIdentity: ...

    async def list_identities(self, *, user_id: UUID) -> list[EnrolledIdentity]:
        """Metadata only -- never returns `template_ciphertext` (Sec11, Sec14:
        `GET /v1/perception/identities` never exposes a template)."""
        ...

    async def get_identity_templates(
        self, *, user_id: UUID, modality: Modality
    ) -> list[EnrolledIdentity]:
        """The one call site permitted to read `template_ciphertext` back --
        `domain/identity_fusion.py`'s matching step (Sec6.2, Sec7.1), never
        an API response path."""
        ...

    async def revoke_identity(self, identity_id: UUID) -> bool:
        """Hard delete of the template row, not a soft-delete flag (Sec11) --
        returns `False` if no such identity exists."""
        ...

    async def grant_consent(self, grant: ConsentGrant) -> ConsentGrant: ...

    async def revoke_consent(self, *, user_id: UUID, source: Source) -> ConsentGrant | None:
        """Returns the revoked grant, or `None` if no active grant existed."""
        ...

    async def consent_status(self, *, user_id: UUID) -> list[ConsentGrant]:
        """Every grant (active and revoked) for the user -- Sec14's
        `GET /v1/perception/consent`."""
        ...

    async def has_active_consent(self, *, user_id: UUID, source: Source) -> bool:
        """Sec11's own gate: no sensor `start()` call succeeds without this
        returning `True` first."""
        ...

    async def record_identity_observation(
        self, observation: IdentityObservation, *, outbox_event: OutboxEvent | None = None
    ) -> IdentityObservation: ...

    async def record_sensor_health(
        self, *, sensor_id: str, sensor_type: str, status: str, capabilities: list[str]
    ) -> None: ...

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID: ...

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Declared for symmetry with every other engine's `domain/ports.py` --
    unused by `domain/` itself; every outbound RPC this engine makes is
    reached through `AIModelOrchestrationPort` above."""

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> EventEnvelope: ...

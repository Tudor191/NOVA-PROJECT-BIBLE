"""Domain entities -- not ORM models (docs/design/phase-2d/
03-perception-engine.md §4). Every model here is either identity/presence/
attention *sensing* state or a narrow audit record of *when* an observation
happened -- never a decision, never rendered content, never a world fact this
engine itself owns (§0.5, §0.6: World Model Engine owns the "current state of
reality" projection this engine only ever publishes toward).

`IdentityObservation` is the append-only, per-correlation-window audit trail
(§8's fusion output, one row per window); `IdentityConfidenceState` is the
separate, continuously-updated *live* state derived from that stream (§0.10,
§8 step 6) -- in-process only, never persisted, mirroring
`communication-engine`'s own `session_registry.py` precedent for exactly this
kind of live, restart-safe-to-lose state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = [
    "AttentionObservation",
    "ConfidenceTier",
    "ConsentGrant",
    "EnrolledIdentity",
    "IdentityConfidenceState",
    "IdentityObservation",
    "Modality",
    "PresenceObservation",
    "Source",
]

Modality = Literal["voice", "face"]
Source = Literal["microphone", "camera"]
ConfidenceTier = Literal["high", "medium", "low", "unknown"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EnrolledIdentity(BaseModel):
    """One enrolled voiceprint/faceprint template (§4.1, §15) -- the Identity
    Registry's own record. `template_ciphertext` is application-level
    encrypted before this model is ever constructed (`domain/enrollment.py`
    owns the encryption boundary, never the repository layer, §16); this
    model never carries a plaintext embedding."""

    identity_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    modality: Modality
    template_ciphertext: bytes
    enrolled_at: datetime = Field(default_factory=_utcnow)
    revoked_at: datetime | None = None


class IdentityObservation(BaseModel):
    """One fused identity verdict for a single correlation window (§4.1, §8).
    Append-only -- immutable once written, the permanent audit trail §0.10's
    continuous reassessment is built on top of, never itself mutated in
    place. `identity_id` is `None` for a confidently-present-but-unmatched
    observation."""

    observation_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    identity_id: UUID | None = None
    fused_confidence: float = Field(ge=0.0, le=1.0)
    confidence_tier: ConfidenceTier
    per_modality_signals: dict[str, object] = Field(default_factory=dict)
    """Open, extensible mapping -- audit trail for trust-through-
    inspectability (§11) and the plug-in point for future evidence sources
    (§0.10, §23: behavioral biometrics, device proximity, environmental
    context, movement patterns, additional modalities) without a
    fusion-function redesign."""
    correlation_id: UUID | None = None
    observed_at: datetime = Field(default_factory=_utcnow)


class IdentityConfidenceState(BaseModel):
    """The current, continuously-updated running state per active presence
    session (§0.10, §4.1, §8 step 6) -- in-process, live state, never a
    Postgres row. Derived entirely from the `IdentityObservation` stream
    (never the reverse) and safe to lose on restart: a fresh fusion sequence
    simply rebuilds it from the next few correlation windows."""

    presence_session_id: UUID
    user_id: UUID
    identity_id: UUID | None = None
    smoothed_confidence: float = Field(ge=0.0, le=1.0)
    smoothed_tier: ConfidenceTier
    observation_count: int = Field(default=0, ge=0)
    last_updated_at: datetime = Field(default_factory=_utcnow)


class PresenceObservation(BaseModel):
    """`perception.presence.observed` (§4.2, §7.2, §13.2)."""

    user_id: UUID | None = None
    present: bool
    confidence: float = Field(ge=0.0, le=1.0)
    source: Source
    observed_at: datetime = Field(default_factory=_utcnow)


class AttentionObservation(BaseModel):
    """`perception.attention.observed` (§4.2, §7.3, §13.2) -- a candidate
    signal for addressee detection (§10), never a verdict."""

    identity_id: UUID | None = None
    attention_state: Literal["engaged", "disengaged", "unknown"]
    gaze_direction: Literal["toward_device", "away", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=_utcnow)


class ConsentGrant(BaseModel):
    """Per-source consent state (§4.3, §11) -- Doc 22 Principle 8's "explicit
    per-source consent before activation, revocable with immediate effect,"
    made concrete."""

    consent_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    source: Source
    scope: str
    granted_at: datetime = Field(default_factory=_utcnow)
    revoked_at: datetime | None = None

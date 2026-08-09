"""Perception Engine event payloads (Bible Part 11), per
docs/design/phase-2d/03-perception-engine.md Sec13.2.

Formalizes ADR-024 registration for all 7 subjects `perception-engine`
already publishes -- `events/publishers.py` there has shaped these as raw,
unvalidated dicts since Phase 2D-B, by explicit, disclosed design ("this
engine's own first real producer act, tracked as a near-term follow-up",
that module's own docstring). This is that follow-up, per
docs/design/phase-2d/04-conversation-intelligence.md Sec0.6: a
**registration**, not a redesign -- every field name and type below is a
verbatim match of `nova_perception_engine.events.publishers`' existing
output as of Phase 2D-C, confirmed by direct code inspection before this
file was written. `perception-engine`'s own publisher functions are cut
over to construct these types (still building the same wire shape they
always have), not the other way around.

`ConfidenceTier` is imported from `nova_contracts.events.personality`
rather than redefined here -- the same shared four-tier vocabulary (Doc 23
Sec5.2 / Bible Part 17's Confidence Expression model), applied to identity
confidence exactly as Doc 22 Principle 7 says it must be ("applies to
identity exactly as it applies to reasoning conclusions"). The numeric
thresholds each engine maps to each tier remain entirely its own --
reusing the vocabulary is not reusing the calibration.

Every payload carries `schema_version: int = 1` from this first commit
(ADR-024).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.events.personality import ConfidenceTier
from nova_contracts.registry import register_payload

__all__ = [
    "AttentionState",
    "ConfidenceTier",
    "GazeDirection",
    "PerceptionAddresseeSignalCandidatePayload",
    "PerceptionAttentionObservedPayload",
    "PerceptionConsentChangedPayload",
    "PerceptionIdentityObservedPayload",
    "PerceptionPresenceObservedPayload",
    "PerceptionSensorHealthChangedPayload",
    "PerceptionSource",
    "PerceptionWakeDetectedPayload",
]


class PerceptionSource(StrEnum):
    """Matches `nova_perception_engine.domain.models.Source` exactly."""

    MICROPHONE = "microphone"
    CAMERA = "camera"


class AttentionState(StrEnum):
    """Matches `AttentionObservation.attention_state`'s existing `Literal`
    exactly."""

    ENGAGED = "engaged"
    DISENGAGED = "disengaged"
    UNKNOWN = "unknown"


class GazeDirection(StrEnum):
    """Matches `AttentionObservation.gaze_direction`'s existing `Literal`
    exactly."""

    TOWARD_DEVICE = "toward_device"
    AWAY = "away"
    UNKNOWN = "unknown"


@register_payload("perception.presence.observed")
class PerceptionPresenceObservedPayload(BaseModel):
    """Matches `PresenceObservation`; wildcard-matched by World Model's
    `perception.*.observed` subscription (`domain/context.py::
    clear_present_identities`, `present=False` case)."""

    user_id: UUID | None = None
    present: bool
    confidence: float = Field(ge=0.0, le=1.0)
    source: PerceptionSource
    schema_version: int = 1


@register_payload("perception.identity.observed")
class PerceptionIdentityObservedPayload(BaseModel):
    """Matches `IdentityConfidenceState`, published only on a
    `smoothed_tier` change, not every correlation window (design doc
    Sec13.2); wildcard-matched by World Model's `perception.*.observed`
    subscription (`domain/context.py::upsert_present_identity`)."""

    user_id: UUID
    identity_id: UUID | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_tier: ConfidenceTier
    modality_summary: str
    schema_version: int = 1


@register_payload("perception.attention.observed")
class PerceptionAttentionObservedPayload(BaseModel):
    """Matches `AttentionObservation` -- a candidate signal for addressee
    detection (design doc Sec10), never a verdict."""

    identity_id: UUID | None = None
    attention_state: AttentionState
    gaze_direction: GazeDirection
    confidence: float = Field(ge=0.0, le=1.0)
    schema_version: int = 1


@register_payload("perception.wake.detected")
class PerceptionWakeDetectedPayload(BaseModel):
    """Deliberately subject-named `.detected`, not `.observed` (design doc
    Sec13.2) -- never matches World Model's `perception.*.observed`
    wildcard."""

    matched: bool
    confidence: float = Field(ge=0.0, le=1.0)
    schema_version: int = 1


@register_payload("perception.addressee_signal.candidate")
class PerceptionAddresseeSignalCandidatePayload(BaseModel):
    """Master Blueprint Sec5 / design doc Sec10 -- raw candidate signals
    only, no verdict field of any kind (`should_respond`/`is_addressed` are
    deliberately absent). Deliberately subject-named `.candidate`, not
    `.observed` -- never matches World Model's wildcard. The sole input
    contract for `communication-engine`'s Phase 2D-C addressee-detection
    fusion (docs/design/phase-2d/04-conversation-intelligence.md Sec4).

    `user_id` (Phase 2D-C Closure Priority 2, docs/design/phase-2d/
    05-conversation-intelligence-closure.md Sec4) -- required, breaking
    addition to an already-registered contract, coordinated same-release
    since `communication-engine` is this payload's only consumer and both
    engines deploy from the same monorepo (Sec12's own migration-strategy
    reasoning). **Deliberately not the same claim as `identity_id`:**
    `user_id` is perception-engine's configured instance owner
    (`Settings.primary_user_id`, ADR-025's single-trusted-user default),
    present on every candidate regardless of whether biometric identity
    matched this window; `identity_id` is a per-window, evidence-scored
    verification result, `None` whenever no match occurred. A future
    consumer must not treat `user_id` as an identity-confidence claim --
    that is what `identity_id`/`identity_confidence` are for."""

    wake_word_matched: bool
    wake_word_confidence: float = Field(ge=0.0, le=1.0)
    identity_id: UUID | None = None
    identity_confidence: float = Field(ge=0.0, le=1.0)
    gaze_direction: GazeDirection
    session_active: bool
    user_id: UUID
    schema_version: int = 1


@register_payload("perception.consent.changed")
class PerceptionConsentChangedPayload(BaseModel):
    """Doc 22 Principle 8 -- explicit per-source consent, revocable at any
    time with immediate effect."""

    user_id: UUID
    source: str
    granted: bool
    schema_version: int = 1


@register_payload("perception.sensor.health_changed")
class PerceptionSensorHealthChangedPayload(BaseModel):
    """`sensor_type`/`status` remain plain `str` here, matching
    `nova_perception_engine`'s own domain layer, which does not constrain
    either to a fixed vocabulary today -- this is a registration of the
    existing shape, not a new constraint (module docstring)."""

    sensor_id: str
    sensor_type: str
    status: str
    schema_version: int = 1

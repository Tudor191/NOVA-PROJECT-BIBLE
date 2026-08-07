"""Personality Engine event payloads (Bible Part 17), per
docs/design/phase-2d/02-personality-engine.md Sec7 (interactions), Sec10
(event contracts), and the boundary Sec0.2/ADR-030 establishes: this engine
stores and applies resolved values, never learns them.

Every payload carries `schema_version: int = 1` from its first commit
(ADR-024), the same discipline every engine's payloads follow since Phase 2A.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from nova_contracts.registry import register_payload


class ConfidenceTier(StrEnum):
    """Mirrors Doc 23 Sec5.2's four confidence levels -- caller-supplied
    (epistemic deference, ADR-028's pattern applied here per design doc
    Sec4): this engine cross-checks phrasing against the tier, it never
    re-derives the tier itself."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CommunicationStyle(StrEnum):
    """Bible Part 13's nine-style palette."""

    PROFESSIONAL = "professional"
    EDUCATIONAL = "educational"
    TECHNICAL = "technical"
    FRIENDLY = "friendly"
    EXECUTIVE = "executive"
    CREATIVE = "creative"
    MINIMAL = "minimal"
    ANALYTICAL = "analytical"
    EMERGENCY = "emergency"


class ViolationCheckFamily(StrEnum):
    """Design doc Sec4's four validator check families."""

    CONFIDENCE_LANGUAGE = "confidence_language"
    FORBIDDEN_PATTERN = "forbidden_pattern"
    EMOTIONAL_STABILITY = "emotional_stability"
    PROFESSIONALISM_FLOOR = "professionalism_floor"


class ViolationRecordPayload(BaseModel):
    """One entry in a `ValidationResult.violations` list (design doc Sec4,
    Sec9's `validation_audit` table)."""

    check_family: ViolationCheckFamily
    detail: str


@register_payload("personality.validate_response.request")
class PersonalityValidateResponseRequestPayload(BaseModel):
    """Event Bus RPC counterpart to `POST /validate` (design doc Sec7.1,
    Sec11) -- the ADR-005 gate's synchronous dependency, called by
    `communication-engine` before every delivered response."""

    content: str
    confidence_tier: ConfidenceTier = ConfidenceTier.UNKNOWN
    session_id: UUID
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("personality.validate_response.reply")
class PersonalityValidateResponseReplyPayload(BaseModel):
    passed: bool
    adjusted_content: str | None = None
    violations: list[ViolationRecordPayload] = Field(default_factory=list)
    schema_version: int = 1


@register_payload("personality.style.select.request")
class PersonalityStyleSelectRequestPayload(BaseModel):
    """Event Bus RPC counterpart to `GET /style` (design doc Sec7.1, Sec11)."""

    situation_hint: str | None = None
    channel: str | None = None
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("personality.style.select.reply")
class PersonalityStyleSelectReplyPayload(BaseModel):
    style: CommunicationStyle
    verbosity: str
    technical_depth: str
    schema_version: int = 1


@register_payload("personality.memory.update")
class PersonalityMemoryUpdatePayload(BaseModel):
    """Inbound from `digital-twin-engine` once it exists (Phase 2D-D) --
    design doc Sec0.2, Sec7.2, ADR-030. Defined now, per ADR-024 versioning
    discipline, unused until Phase 2D-D ships; this engine's own Personality
    Memory (design doc Sec6) is a static default until then."""

    verbosity: str | None = None
    technical_depth: str | None = None
    terminology_preference: dict[str, Any] | None = None
    source: str = "digital_twin"
    schema_version: int = 1

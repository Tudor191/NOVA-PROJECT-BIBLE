"""Domain entities -- not ORM models (docs/design/phase-2d/
02-personality-engine.md Sec1, Sec3-Sec6).

**The boundary this file exists to enforce** (design doc Sec0.1-Sec0.3, Doc 23,
ADR-030): every model here is either the fixed Core Identity (Doc 23 Sec2's
traits/values, changed only by a Doc 23 amendment, never by this engine's own
runtime logic), the deterministic output of a rule-based check, or the current
*resolved* value of an expression preference this engine applies but never
learns. If a future change to this file would make it accumulate evidence,
track confidence over time, or detect a preference from behavior, it belongs
in `digital-twin-engine` instead (ADR-030).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = [
    "CommunicationStyle",
    "ConfidenceTier",
    "CoreIdentity",
    "IdentitySnapshot",
    "MemoryProfile",
    "ValidationResult",
    "ViolationCheckFamily",
    "ViolationRecord",
]


class ConfidenceTier(StrEnum):
    """Doc 23 Sec5.2's four confidence levels -- caller-supplied, never
    re-derived by this engine (design doc Sec4.1's epistemic-deference
    pattern, mirroring ADR-028's for Executive Cognition)."""

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


class CoreIdentity(BaseModel):
    """Design doc Sec3 -- a singleton, versioned configuration record. Doc 23
    Sec2's twelve traits and eight values, plus the forbidden-behavior list
    Sec4's validator checks against. Changes only on a Doc 23 amendment
    (Doc 23's own closing section), never through this engine's runtime."""

    schema_version: int = 1
    traits: list[str]
    values: list[str]
    forbidden_behaviors: list[str]
    version_note: str


class ViolationRecord(BaseModel):
    """One finding from the Consistency Validator (design doc Sec4)."""

    check_family: ViolationCheckFamily
    detail: str


class ValidationResult(BaseModel):
    """Design doc Sec4's validator output. `passed=False` means the content
    must not be delivered as originally supplied -- design doc Sec8's one
    hard-stop failure path, distinct from `communication-engine`'s own
    deliver-with-fallback behavior for an unreachable RPC."""

    passed: bool
    adjusted_content: str | None = None
    violations: list[ViolationRecord] = Field(default_factory=list)


class MemoryProfile(BaseModel):
    """Design doc Sec6 -- the current *resolved* expression profile. A
    static default until Phase 2D-D's `digital-twin-engine` exists to
    publish real values (ADR-030); `source` distinguishes the two so the
    transition is observable, never silent."""

    verbosity: str = "moderate"
    technical_depth: str = "moderate"
    terminology_preference: dict[str, Any] | None = None
    source: str = "static_default"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdentitySnapshot(BaseModel):
    """Design doc Sec11, Sec13 -- the cacheable summary
    `communication-engine`'s fast-path (that document's Sec13) uses instead
    of a full `validate_response` round trip for low-stakes acknowledgment
    content. Derived entirely from `CoreIdentity` + the current
    `MemoryProfile`, never independent state of its own."""

    id: UUID = Field(default_factory=uuid4)
    traits: list[str]
    default_style: CommunicationStyle
    verbosity: str
    technical_depth: str

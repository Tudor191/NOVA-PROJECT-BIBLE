"""Sensory Memory -- docs/design/phase-1/01-memory-engine.md §2. Capture-then-
discard-unless-promoted: an in-process buffer only, never persisted itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

MIN_CONTENT_LENGTH = 8


@dataclass(frozen=True)
class SensoryCandidate:
    content: str
    source: str
    user_id: UUID
    project_id: UUID | None = None
    source_ref: UUID | None = None
    explicit_worth_retaining: bool | None = None
    """Set by a caller that already has an opinion (e.g. Reasoning Engine, once it
    exists) -- when `None`, `worth_retaining` falls back to a Phase 1 heuristic."""


def worth_retaining(candidate: SensoryCandidate) -> bool:
    """Whether `candidate` is worth promoting into a persisted memory.

    Real intent-based classification is Reasoning Engine's job from Phase 2 onward
    (docs/design/phase-1/01-memory-engine.md §7, §20); this is a deliberately
    conservative Phase 1 placeholder -- an explicit caller-supplied verdict wins if
    given, otherwise a minimal length heuristic keeps trivially short observations
    (e.g. a bare acknowledgement) from becoming memory rows.
    """
    if candidate.explicit_worth_retaining is not None:
        return candidate.explicit_worth_retaining
    return len(candidate.content.strip()) >= MIN_CONTENT_LENGTH

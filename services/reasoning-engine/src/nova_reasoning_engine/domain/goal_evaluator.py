"""Goal Evaluation (docs/design/phase-2b/00-reasoning-engine.md §8) -- scores an
`Alternative`'s alignment against Current Goals. Structural, never a model call
-- the same discipline every *scoring* mechanism in this design follows (§9,
§10, §15, §16); only *generation* steps (§12) legitimately call a model.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import Alternative, Goal

__all__ = ["goal_alignment_score"]


def _keyword_overlap(a: str, b: str) -> float:
    """Fraction of `a`'s words also present in `b`, case-insensitive -- the
    simplest honest overlap heuristic that requires no external dependency;
    an embedding-similarity upgrade is a natural future refinement, not
    invented ahead of a real need."""
    words_a = {w for w in a.lower().split() if w}
    words_b = {w for w in b.lower().split() if w}
    if not words_a:
        return 0.0
    return len(words_a & words_b) / len(words_a)


def goal_alignment_score(alternative: Alternative, goals: list[Goal]) -> float | None:
    """§8: a `priority`-weighted average of how well `alternative.description`
    overlaps with each goal's own description. Returns `None` (never a
    defaulted neutral score) when no goals were supplied -- absence must stay
    visible in the Decision Matrix (§15), not silently pretend goal-alignment
    was considered when it wasn't."""
    if not goals:
        return None
    total_priority = sum(goal.priority for goal in goals)
    if total_priority <= 0.0:
        return None
    weighted = sum(
        goal.priority * _keyword_overlap(goal.description, alternative.description)
        for goal in goals
    )
    return round(weighted / total_priority, 4)

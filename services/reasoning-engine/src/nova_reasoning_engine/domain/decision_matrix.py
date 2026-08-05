"""Decision Scoring (docs/design/phase-2b/00-reasoning-engine.md §15) -- Bible
Part 8's Decision Matrix, a fixed, weighted, multi-criteria formula. Structural,
like every other *scoring* mechanism in this design (§8, §9, §10, §16), never a
model call.

**Honest scope note.** Only `accuracy` and `reliability` have a real,
structural signal available in Phase 2B: the supporting `Evidence`'s own
weight. The remaining nine Bible-named criteria (complexity, maintainability,
performance, security, scalability, development_effort, future_flexibility,
cost, user_experience, compatibility) have no structured per-alternative data
source yet -- Bible Part 8 names them as dimensions a mature Decision Matrix
scores, but nothing in this engine's own domain model (or any upstream port)
currently produces a real signal for them. They are scored at a fixed neutral
midpoint (`_NEUTRAL_SCORE`) rather than fabricated from nothing, and this is
named here explicitly rather than left to look like real computed precision.
A Capability Engine or richer `Alternative` metadata is the natural future
source for these (§25).
"""

from __future__ import annotations

from uuid import UUID

from nova_reasoning_engine.domain.models import Alternative, DecisionMatrixScores, Evidence

__all__ = ["rank_alternatives", "score_alternative"]

_NEUTRAL_SCORE = 0.5

# Weighted-sum coefficients for the composite score. `goal_alignment` is
# excluded from the weighted average entirely when `None` (§8) -- the same
# "absence is visible, never silently defaulted" discipline as confidence
# estimation (§10).
_WEIGHTS: dict[str, float] = {
    "accuracy": 0.20,
    "complexity": 0.05,
    "maintainability": 0.05,
    "performance": 0.05,
    "security": 0.10,
    "scalability": 0.05,
    "development_effort": 0.05,
    "future_flexibility": 0.05,
    "cost": 0.05,
    "user_experience": 0.05,
    "compatibility": 0.05,
    "reliability": 0.15,
    "goal_alignment": 0.10,
}


def _supporting_evidence_weight(
    alternative: Alternative, evidence_by_id: dict[UUID, Evidence]
) -> float:
    weights = [
        evidence_by_id[eid].weight
        for eid in alternative.supporting_evidence_ids
        if eid in evidence_by_id
    ]
    if not weights:
        return 0.0
    return round(sum(weights) / len(weights), 4)


def _reliability(alternative: Alternative, evidence_by_id: dict[UUID, Evidence]) -> float:
    weights = [
        evidence_by_id[eid].weight
        for eid in alternative.supporting_evidence_ids
        if eid in evidence_by_id
    ]
    if not weights:
        return 0.0
    strong = sum(1 for w in weights if w >= 0.5)
    return round(strong / len(weights), 4)


def score_alternative(
    alternative: Alternative,
    *,
    evidence_by_id: dict[UUID, Evidence],
    goal_alignment: float | None,
) -> DecisionMatrixScores:
    """Scores one `Alternative` across all twelve Bible-named criteria plus
    Goal Alignment (§8), producing the `composite` the pipeline ranks on."""
    accuracy = _supporting_evidence_weight(alternative, evidence_by_id)
    reliability = _reliability(alternative, evidence_by_id)

    factors: dict[str, float | None] = {
        "accuracy": accuracy,
        "complexity": _NEUTRAL_SCORE,
        "maintainability": _NEUTRAL_SCORE,
        "performance": _NEUTRAL_SCORE,
        "security": _NEUTRAL_SCORE,
        "scalability": _NEUTRAL_SCORE,
        "development_effort": _NEUTRAL_SCORE,
        "future_flexibility": _NEUTRAL_SCORE,
        "cost": _NEUTRAL_SCORE,
        "user_experience": _NEUTRAL_SCORE,
        "compatibility": _NEUTRAL_SCORE,
        "reliability": reliability,
        "goal_alignment": goal_alignment,
    }
    present = {k: v for k, v in factors.items() if v is not None}
    total_weight = sum(_WEIGHTS[k] for k in present)
    composite = (
        round(sum(_WEIGHTS[k] * v for k, v in present.items()) / total_weight, 4)
        if total_weight > 0.0
        else 0.0
    )

    return DecisionMatrixScores(
        accuracy=accuracy,
        complexity=_NEUTRAL_SCORE,
        maintainability=_NEUTRAL_SCORE,
        performance=_NEUTRAL_SCORE,
        security=_NEUTRAL_SCORE,
        scalability=_NEUTRAL_SCORE,
        development_effort=_NEUTRAL_SCORE,
        future_flexibility=_NEUTRAL_SCORE,
        cost=_NEUTRAL_SCORE,
        user_experience=_NEUTRAL_SCORE,
        compatibility=_NEUTRAL_SCORE,
        reliability=reliability,
        goal_alignment=goal_alignment,
        composite=composite,
    )


def rank_alternatives(alternatives: list[Alternative]) -> list[Alternative]:
    """Highest `matrix_scores.composite` first. Ties break on `alternative.id`
    ascending -- the identical stable-tiebreak discipline ADR-021 established
    for model routing (§15), reused here because the underlying requirement
    (reproducible, explainable selection among equally-scored candidates) is
    the same one layer up the cognitive stack. Alternatives with no score yet
    sort last."""
    return sorted(
        alternatives,
        key=lambda a: (
            -(a.matrix_scores.composite if a.matrix_scores is not None else float("-inf")),
            str(a.id),
        ),
    )

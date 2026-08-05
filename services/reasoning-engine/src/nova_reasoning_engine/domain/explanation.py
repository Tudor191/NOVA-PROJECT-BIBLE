"""Decision Explanation (docs/design/phase-2b/00-reasoning-engine.md §16) --
derives `DecisionExplanation` from already-computed structured fields, never
authored independently. The identical discipline ADR-021 established for
`RoutingDecision.explanation` in the AI Model Orchestration Engine, reused
verbatim because it is the same underlying requirement: an explanation that
can never claim something the structured data doesn't support.
"""

from __future__ import annotations

from uuid import UUID

from nova_reasoning_engine.domain.models import (
    Alternative,
    ConfidenceBreakdown,
    DecisionExplanation,
    Evidence,
)

__all__ = ["derive_explanation"]

_FRIENDLY_NAMES: dict[str, str] = {
    "accuracy": "accuracy",
    "reliability": "reliability",
    "goal_alignment": "goal alignment",
    "complexity": "complexity",
    "maintainability": "maintainability",
    "performance": "performance",
    "security": "security",
    "scalability": "scalability",
    "development_effort": "development effort",
    "future_flexibility": "future flexibility",
    "cost": "cost",
    "user_experience": "user experience",
    "compatibility": "compatibility",
}

_CONFIDENCE_FRIENDLY_NAMES: dict[str, str] = {
    "evidence_quality": "evidence quality",
    "evidence_quantity": "evidence quantity",
    "historical_success": "historical success rate",
    "model_agreement": "model agreement",
    "memory_consistency": "memory consistency",
    "knowledge_quality": "knowledge quality",
    "reasoning_completeness": "reasoning completeness",
    "predicted_uncertainty": "predicted uncertainty",
}


def _chosen_reason(chosen: Alternative) -> str:
    if chosen.matrix_scores is None:
        return f"Selected {chosen.description!r} (no matrix score computed)."
    scores = chosen.matrix_scores
    factor_values = {
        name: getattr(scores, field)
        for field, name in _FRIENDLY_NAMES.items()
        if getattr(scores, field) is not None
    }
    top_factors = sorted(factor_values.items(), key=lambda kv: kv[1], reverse=True)[:3]
    reasons = ", ".join(f"{name} ({value:.2f})" for name, value in top_factors)
    return f"Selected for its {reasons} (composite {scores.composite:.2f})."


def _rejected_reasons(
    chosen: Alternative,
    alternatives: list[Alternative],
    constraint_violations: dict[str, list[str]],
) -> dict[UUID, str]:
    reasons: dict[UUID, str] = {}
    chosen_composite = chosen.matrix_scores.composite if chosen.matrix_scores else 0.0
    for alt in alternatives:
        if alt.id == chosen.id:
            continue
        violated = constraint_violations.get(str(alt.id))
        if violated:
            reasons[alt.id] = f"Violates constraint(s): {', '.join(violated)}."
        elif alt.matrix_scores is None:
            reasons[alt.id] = "No matrix score computed."
        else:
            reasons[alt.id] = (
                f"Lower composite score ({alt.matrix_scores.composite:.2f} vs "
                f"{chosen_composite:.2f})."
            )
    return reasons


def _strongest_evidence(
    chosen: Alternative, evidence_by_id: dict[UUID, Evidence], *, top_n: int = 3
) -> list[UUID]:
    supporting = [
        evidence_by_id[eid] for eid in chosen.supporting_evidence_ids if eid in evidence_by_id
    ]
    supporting.sort(key=lambda e: e.weight, reverse=True)
    return [e.id for e in supporting[:top_n]]


def _remaining_uncertainty(confidence: ConfidenceBreakdown) -> str:
    factors = {
        name: getattr(confidence, field)
        for field, name in _CONFIDENCE_FRIENDLY_NAMES.items()
        if getattr(confidence, field) is not None
    }
    if not factors:
        return "No confidence factors were available to assess remaining uncertainty."
    weakest_name, weakest_value = min(factors.items(), key=lambda kv: kv[1])
    return (
        f"{weakest_name.capitalize()} is the largest source of remaining "
        f"uncertainty ({weakest_value:.2f})."
    )


def derive_explanation(
    *,
    chosen: Alternative,
    alternatives: list[Alternative],
    evidence_by_id: dict[UUID, Evidence],
    constraint_violations: dict[str, list[str]],
    confidence: ConfidenceBreakdown,
) -> DecisionExplanation:
    """§16, in full: chosen_reason, rejected_reasons, strongest_evidence, and
    remaining_uncertainty -- every field mechanically populated from data
    already computed earlier in the pipeline (§9, §13, §15, §10)."""
    return DecisionExplanation(
        chosen_reason=_chosen_reason(chosen),
        rejected_reasons=_rejected_reasons(chosen, alternatives, constraint_violations),
        strongest_evidence=_strongest_evidence(chosen, evidence_by_id),
        remaining_uncertainty=_remaining_uncertainty(confidence),
    )

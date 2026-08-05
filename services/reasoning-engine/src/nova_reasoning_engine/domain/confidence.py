"""Confidence Estimation (docs/design/phase-2b/00-reasoning-engine.md §10) --
Bible Part 8's seven confidence factors, implemented as a structural weighted
formula. Confidence is never estimated by asking a model how confident it is
-- a model's self-reported confidence is exactly the kind of unverified signal
Part 8's own "UNCERTAINTY MANAGEMENT" section warns against. The same
non-circular discipline the AI Model Orchestration Engine's `estimate_complexity`
established in Phase 2A.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import (
    Alternative,
    ConfidenceBreakdown,
    Evidence,
    KnowledgeReference,
    MemoryReference,
)

__all__ = ["estimate_confidence"]

# Weighted-sum coefficients for the factors that are always present. `historical_
# success` and `model_agreement` are excluded from the weighted average entirely
# when `None` (§10) -- their weight is redistributed proportionally across the
# remaining present factors rather than silently treated as a zero score.
_BASE_WEIGHTS: dict[str, float] = {
    "evidence_quality": 0.20,
    "evidence_quantity": 0.10,
    "historical_success": 0.15,
    "model_agreement": 0.10,
    "memory_consistency": 0.15,
    "knowledge_quality": 0.15,
    "reasoning_completeness": 0.10,
    "predicted_uncertainty": 0.05,
}

_EXPECTED_EVIDENCE_COUNT = 5
"""§10's `evidence_quantity` reference point -- a fixed, honestly-approximate
target (mirrors the AI Model Orchestration Engine's own fixed reference points
for complexity estimation), not a learned threshold."""


def _evidence_quality(evidence: list[Evidence]) -> float:
    if not evidence:
        return 0.0
    return round(sum(e.weight for e in evidence) / len(evidence), 4)


def _evidence_quantity(evidence: list[Evidence]) -> float:
    return round(min(1.0, len(evidence) / _EXPECTED_EVIDENCE_COUNT), 4)


def _memory_consistency(memories: list[MemoryReference]) -> float:
    """Fraction of retrieved memories that don't conflict. Phase 2B has no
    contradiction-detection mechanism of its own for memories (that is
    Knowledge Engine's job for knowledge, and no equivalent exists yet for
    Memory) -- with nothing to flag a conflict, every retrieved memory counts
    as consistent. A dedicated conflict signal is a natural extension once
    `MemoryPort` can surface one (§25), not fabricated here."""
    return 1.0 if memories else 0.0


def _knowledge_quality(knowledge: list[KnowledgeReference]) -> float:
    """Derived from Knowledge Engine's own maturity-stage field (`layer`,
    Phase 1, ADR-015) -- later stages are more mature, hence higher quality."""
    if not knowledge:
        return 0.0
    stage_score = {
        "raw": 0.15,
        "processed": 0.30,
        "verified": 0.55,
        "connected": 0.70,
        "applied": 0.85,
        "expert": 0.95,
        "strategic": 1.0,
    }
    scores = [stage_score.get(ref.layer, 0.3) for ref in knowledge]
    return round(sum(scores) / len(scores), 4)


def _predicted_uncertainty(alternatives: list[Alternative]) -> float:
    """Inverse of the decision-matrix score spread between the top two
    alternatives -- a close call is definitionally less certain than a
    landslide. `0.5` (neither certain nor uncertain) when fewer than two
    scored alternatives exist to compare."""
    scored = sorted(
        (a.matrix_scores.composite for a in alternatives if a.matrix_scores is not None),
        reverse=True,
    )
    if len(scored) < 2:
        return 0.5
    spread = scored[0] - scored[1]
    return round(max(0.0, 1.0 - spread), 4)


def _reasoning_completeness(*, degraded_steps: int, total_steps: int) -> float:
    if total_steps <= 0:
        return 1.0
    return round(max(0.0, (total_steps - degraded_steps) / total_steps), 4)


def _weighted_composite(factors: dict[str, float | None]) -> float:
    present = {k: v for k, v in factors.items() if v is not None}
    if not present:
        return 0.0
    total_weight = sum(_BASE_WEIGHTS[k] for k in present)
    if total_weight <= 0.0:
        return 0.0
    return round(sum(_BASE_WEIGHTS[k] * v for k, v in present.items()) / total_weight, 4)


def estimate_confidence(
    *,
    evidence: list[Evidence],
    memories: list[MemoryReference],
    knowledge: list[KnowledgeReference],
    alternatives: list[Alternative],
    historical_success: float | None = None,
    model_agreement: float | None = None,
    degraded_steps: int = 0,
    total_steps: int = 1,
) -> ConfidenceBreakdown:
    """§10, in full. `historical_success` and `model_agreement` are left `None`
    by callers until real signal exists (§25's outcome-reporting extension
    point for the former; the latter requires >1 converging hypothesis, §12)."""
    factors: dict[str, float | None] = {
        "evidence_quality": _evidence_quality(evidence),
        "evidence_quantity": _evidence_quantity(evidence),
        "historical_success": historical_success,
        "model_agreement": model_agreement,
        "memory_consistency": _memory_consistency(memories),
        "knowledge_quality": _knowledge_quality(knowledge),
        "reasoning_completeness": _reasoning_completeness(
            degraded_steps=degraded_steps, total_steps=total_steps
        ),
        "predicted_uncertainty": _predicted_uncertainty(alternatives),
    }
    return ConfidenceBreakdown(
        evidence_quality=factors["evidence_quality"] or 0.0,
        evidence_quantity=factors["evidence_quantity"] or 0.0,
        historical_success=historical_success,
        model_agreement=model_agreement,
        memory_consistency=factors["memory_consistency"] or 0.0,
        knowledge_quality=factors["knowledge_quality"] or 0.0,
        reasoning_completeness=factors["reasoning_completeness"] or 0.0,
        predicted_uncertainty=factors["predicted_uncertainty"] or 0.0,
        composite=_weighted_composite(factors),
    )

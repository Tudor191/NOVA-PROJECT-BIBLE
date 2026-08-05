"""Focused unit tests for the core structural-scoring domain modules in
isolation (docs/design/phase-2b/00-reasoning-engine.md §24): the confidence
formula against known factor combinations, decision-matrix scoring
reproducibility, explanation derivation never claiming an unsupported
reason, and constraint hard-gating never leaking a violating alternative
through.
"""

from __future__ import annotations

from uuid import uuid4

from nova_reasoning_engine.domain import confidence as confidence_module
from nova_reasoning_engine.domain import decision_matrix, goal_evaluator
from nova_reasoning_engine.domain import explanation as explanation_module
from nova_reasoning_engine.domain.models import (
    Alternative,
    ConfidenceBreakdown,
    Constraint,
    Evidence,
    Goal,
)


def test_confidence_excludes_none_factors_from_the_weighted_average() -> None:
    evidence = [Evidence(hypothesis_id=uuid4(), source="memory", source_ref="m1", weight=0.8)]
    with_history = confidence_module.estimate_confidence(
        evidence=evidence, memories=[], knowledge=[], alternatives=[], historical_success=1.0
    )
    without_history = confidence_module.estimate_confidence(
        evidence=evidence, memories=[], knowledge=[], alternatives=[], historical_success=None
    )
    assert with_history.historical_success == 1.0
    assert without_history.historical_success is None
    # A perfect historical_success can only raise (or leave unchanged) the composite
    # relative to the same inputs with that factor absent -- never lower it.
    assert with_history.composite >= without_history.composite


def test_confidence_is_reproducible_for_identical_inputs() -> None:
    evidence = [Evidence(hypothesis_id=uuid4(), source="memory", source_ref="m1", weight=0.6)]
    first = confidence_module.estimate_confidence(
        evidence=evidence, memories=[], knowledge=[], alternatives=[]
    )
    second = confidence_module.estimate_confidence(
        evidence=evidence, memories=[], knowledge=[], alternatives=[]
    )
    assert first.composite == second.composite


def test_decision_matrix_scoring_is_reproducible() -> None:
    process_id = uuid4()
    evidence = Evidence(hypothesis_id=uuid4(), source="memory", source_ref="m1", weight=0.7)
    alt = Alternative(
        reasoning_process_id=process_id,
        hypothesis_id=uuid4(),
        description="an alternative",
        supporting_evidence_ids=[evidence.id],
    )
    evidence_by_id = {evidence.id: evidence}

    first = decision_matrix.score_alternative(
        alt, evidence_by_id=evidence_by_id, goal_alignment=None
    )
    second = decision_matrix.score_alternative(
        alt, evidence_by_id=evidence_by_id, goal_alignment=None
    )
    assert first.composite == second.composite
    assert first.goal_alignment is None  # absent, never defaulted to a neutral score (§8)


def test_decision_matrix_rank_breaks_ties_on_id_ascending() -> None:
    process_id = uuid4()
    scores = decision_matrix.DecisionMatrixScores(
        accuracy=0.5, complexity=0.5, maintainability=0.5, performance=0.5, security=0.5,
        scalability=0.5, development_effort=0.5, future_flexibility=0.5, cost=0.5,
        user_experience=0.5, compatibility=0.5, reliability=0.5, composite=0.5,
    )
    alt_a = Alternative(
        id=uuid4(), reasoning_process_id=process_id, hypothesis_id=uuid4(),
        description="a", matrix_scores=scores,
    )
    alt_b = Alternative(
        id=uuid4(), reasoning_process_id=process_id, hypothesis_id=uuid4(),
        description="b", matrix_scores=scores,
    )
    ranked = decision_matrix.rank_alternatives([alt_b, alt_a])
    expected_first = alt_a if str(alt_a.id) < str(alt_b.id) else alt_b
    assert ranked[0].id == expected_first.id


def test_goal_alignment_score_omitted_when_priorities_sum_to_zero() -> None:
    process_id = uuid4()
    alt = Alternative(
        reasoning_process_id=process_id, hypothesis_id=uuid4(), description="ship the fix"
    )
    zero_priority_goal = Goal(id=uuid4(), description="ship the fix", priority=0.0)
    assert goal_evaluator.goal_alignment_score(alt, [zero_priority_goal]) is None
    assert goal_evaluator.goal_alignment_score(alt, []) is None


def test_explanation_never_gives_the_chosen_alternative_a_rejected_reason() -> None:
    process_id = uuid4()
    evidence = Evidence(hypothesis_id=uuid4(), source="memory", source_ref="m1", weight=0.9)
    scores = decision_matrix.DecisionMatrixScores(
        accuracy=0.9, complexity=0.5, maintainability=0.5, performance=0.5, security=0.5,
        scalability=0.5, development_effort=0.5, future_flexibility=0.5, cost=0.5,
        user_experience=0.5, compatibility=0.5, reliability=0.9, composite=0.9,
    )
    chosen = Alternative(
        reasoning_process_id=process_id, hypothesis_id=uuid4(), description="winner",
        supporting_evidence_ids=[evidence.id], matrix_scores=scores,
    )
    rejected = Alternative(
        reasoning_process_id=process_id, hypothesis_id=uuid4(), description="loser",
        matrix_scores=scores.model_copy(update={"composite": 0.1}),
    )
    confidence = ConfidenceBreakdown(
        evidence_quality=0.9, evidence_quantity=0.5, memory_consistency=1.0,
        knowledge_quality=0.6, reasoning_completeness=1.0, predicted_uncertainty=0.2,
        composite=0.8,
    )
    result = explanation_module.derive_explanation(
        chosen=chosen,
        alternatives=[chosen, rejected],
        evidence_by_id={evidence.id: evidence},
        constraint_violations={},
        confidence=confidence,
    )
    assert chosen.id not in result.rejected_reasons
    assert rejected.id in result.rejected_reasons
    assert result.strongest_evidence == [evidence.id]


def test_explanation_names_the_specific_violated_constraint() -> None:
    process_id = uuid4()
    scores = decision_matrix.DecisionMatrixScores(
        accuracy=0.5, complexity=0.5, maintainability=0.5, performance=0.5, security=0.5,
        scalability=0.5, development_effort=0.5, future_flexibility=0.5, cost=0.5,
        user_experience=0.5, compatibility=0.5, reliability=0.5, composite=0.5,
    )
    chosen = Alternative(
        reasoning_process_id=process_id, hypothesis_id=uuid4(), description="winner",
        matrix_scores=scores,
    )
    rejected = Alternative(
        reasoning_process_id=process_id, hypothesis_id=uuid4(), description="over budget",
        constraint_status="rejected_constraint_violation",
    )
    confidence = ConfidenceBreakdown(
        evidence_quality=0.5, evidence_quantity=0.5, memory_consistency=1.0,
        knowledge_quality=0.5, reasoning_completeness=1.0, predicted_uncertainty=0.5,
        composite=0.5,
    )
    constraint = Constraint(kind="budget", description="under $10", hard=True)
    result = explanation_module.derive_explanation(
        chosen=chosen,
        alternatives=[chosen, rejected],
        evidence_by_id={},
        constraint_violations={str(rejected.id): [constraint.description]},
        confidence=confidence,
    )
    assert constraint.description in result.rejected_reasons[rejected.id]

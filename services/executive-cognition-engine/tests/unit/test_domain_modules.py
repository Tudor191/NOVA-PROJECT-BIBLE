"""Focused unit tests for the core structural-scoring domain modules in
isolation (docs/design/phase-2c/00-executive-cognition-engine.md §24): the
Cognitive Priority Matrix formula against known factor combinations,
long-term-alignment scoring, conflict resolution's five-signal procedure,
context-switch evaluation, and failure-recovery action mapping.
"""

from __future__ import annotations

from uuid import uuid4

from nova_executive_cognition_engine.domain import (
    context_switching,
    failure_recovery,
    goal_correlation,
    policy,
    priority,
)
from nova_executive_cognition_engine.domain.conflict_resolution import (
    ConflictSide,
    resolve_conflict,
)
from nova_executive_cognition_engine.domain.models import ExecutiveRequest, FailureAction, Goal


def _request(**overrides: object) -> ExecutiveRequest:
    defaults: dict[str, object] = dict(
        requesting_engine="reasoning-engine",
        request_kind="reasoning_process",
        user_id=uuid4(),
        urgency=0.5,
        importance=0.5,
        complexity=0.5,
        risk=0.5,
        learning_value=0.5,
        resource_cost=0.5,
        user_impact=0.5,
    )
    defaults.update(overrides)
    return ExecutiveRequest(**defaults)


# --- priority.score ----------------------------------------------------------


def test_score_is_reproducible_for_identical_inputs() -> None:
    request = _request(urgency=0.8, importance=0.7)
    first = priority.score(request, long_term_alignment=0.3)
    second = priority.score(request, long_term_alignment=0.3)
    assert first.composite == second.composite


def test_score_inverts_complexity_and_resource_cost() -> None:
    cheap_simple = _request(complexity=0.1, resource_cost=0.1)
    expensive_complex = _request(complexity=0.9, resource_cost=0.9)
    cheap_score = priority.score(cheap_simple, long_term_alignment=0.0)
    expensive_score = priority.score(expensive_complex, long_term_alignment=0.0)
    # All else equal, lower complexity/resource_cost should score higher --
    # they are costs to pay, not reasons to go first (§6).
    assert cheap_score.composite > expensive_score.composite


def test_score_carries_long_term_alignment_through_unmodified() -> None:
    request = _request()
    result = priority.score(request, long_term_alignment=0.42)
    assert result.long_term_alignment == 0.42


# --- goal_correlation.long_term_alignment -------------------------------------


def test_long_term_alignment_is_zero_with_no_goal() -> None:
    request = _request()
    assert goal_correlation.long_term_alignment(request, None, []) == 0.0


def test_long_term_alignment_favors_established_over_ad_hoc_goals() -> None:
    request = _request()
    established = Goal(id=uuid4(), description="", priority=0.5, goal_tier="established")
    ad_hoc = Goal(id=uuid4(), description="", priority=0.5, goal_tier="ad_hoc")
    established_score = goal_correlation.long_term_alignment(request, established, [])
    ad_hoc_score = goal_correlation.long_term_alignment(request, ad_hoc, [])
    assert established_score > ad_hoc_score


def test_long_term_alignment_sibling_boost_is_capped() -> None:
    request = _request()
    goal = Goal(id=uuid4(), description="", priority=0.5, goal_tier="ad_hoc")
    many_siblings = [_request() for _ in range(50)]
    boosted = goal_correlation.long_term_alignment(request, goal, many_siblings)
    assert boosted <= 1.0


# --- conflict_resolution.resolve_conflict -------------------------------------


def test_resolve_conflict_decides_on_evidence_count_first() -> None:
    side_a = ConflictSide(correlation_id=uuid4(), evidence_count=5, confidence_score=0.5)
    side_b = ConflictSide(correlation_id=uuid4(), evidence_count=1, confidence_score=0.9)
    # side_b has higher confidence but fewer evidence items -- evidence wins first (§10).
    winner, signals = resolve_conflict(side_a, side_b, policies=[])
    assert winner == side_a.correlation_id
    assert "cited more evidence" in (signals.evidence_comparison or "")


def test_resolve_conflict_falls_through_to_confidence_when_evidence_ties() -> None:
    side_a = ConflictSide(correlation_id=uuid4(), evidence_count=3, confidence_score=0.4)
    side_b = ConflictSide(correlation_id=uuid4(), evidence_count=3, confidence_score=0.8)
    winner, signals = resolve_conflict(side_a, side_b, policies=[])
    assert winner == side_b.correlation_id
    assert signals.evidence_comparison == "tied"


def test_resolve_conflict_escalates_when_all_five_signals_are_inconclusive() -> None:
    side_a = ConflictSide(correlation_id=uuid4())
    side_b = ConflictSide(correlation_id=uuid4())
    winner, signals = resolve_conflict(side_a, side_b, policies=[])
    assert winner is None
    assert signals.historical_outcome_signal == "tied or unavailable"


def test_resolve_conflict_safety_policy_prefers_lower_risk() -> None:
    side_a = ConflictSide(correlation_id=uuid4(), confidence_score=0.5, risk=0.8)
    side_b = ConflictSide(correlation_id=uuid4(), confidence_score=0.5, risk=0.2)
    winner, signals = resolve_conflict(side_a, side_b, policies=list(policy.DEFAULT_POLICIES))
    assert winner == side_b.correlation_id
    assert signals.policy_applied == "safety_overrides_speed"


# --- context_switching.evaluate_context_switch --------------------------------


def test_context_switch_recommended_when_benefit_exceeds_costs() -> None:
    evaluation = context_switching.evaluate_context_switch(
        current_progress=0.2, recovery_cost=0.1, interruption_impact=0.1, potential_benefit=0.5
    )
    assert evaluation.switch_recommended is True


def test_context_switch_not_recommended_when_costs_exceed_benefit() -> None:
    evaluation = context_switching.evaluate_context_switch(
        current_progress=0.9, recovery_cost=0.4, interruption_impact=0.4, potential_benefit=0.5
    )
    assert evaluation.switch_recommended is False


# --- failure_recovery.recommend_recovery --------------------------------------


def test_recommend_recovery_maps_each_named_stage() -> None:
    assert (
        failure_recovery.recommend_recovery(stage="context_gathering", reason="timeout").action
        is FailureAction.RESTART
    )
    assert (
        failure_recovery.recommend_recovery(
            stage="request_validation", reason="missing urgency"
        ).action
        is FailureAction.REQUEST_CLARIFICATION
    )
    assert (
        failure_recovery.recommend_recovery(
            stage="conflict_resolution", reason="all signals inconclusive"
        ).action
        is FailureAction.ESCALATE_DEEPER
    )
    assert (
        failure_recovery.recommend_recovery(stage="unknown_stage", reason="?").action
        is FailureAction.RESTART
    )

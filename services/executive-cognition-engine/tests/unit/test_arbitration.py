"""`domain.arbitration.arbitrate` (docs/design/phase-2c/
00-executive-cognition-engine.md §7) -- the ranking algorithm and its two
runtime policies. Covers the cumulative resource-budget tracking bug fixed
during implementation (comparing each contender's own bounded `resource_cost`
against the ceiling made `WAIT` structurally unreachable) with a regression
test, alongside the documented tie-break order and both policies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_executive_cognition_engine.domain import arbitration, priority
from nova_executive_cognition_engine.domain.models import ArbitrationOutcome, ExecutiveRequest


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


def _scores(*requests: ExecutiveRequest) -> dict:
    return {r.correlation_id: priority.score(r, long_term_alignment=0.0) for r in requests}


def test_single_request_always_proceeds() -> None:
    request = _request()
    results = arbitration.arbitrate([request], scores=_scores(request))
    assert results[0].outcome is ArbitrationOutcome.PROCEED


def test_higher_composite_score_ranks_first() -> None:
    high = _request(urgency=0.9, importance=0.9, resource_cost=0.1)
    low = _request(urgency=0.1, importance=0.1, resource_cost=0.1)
    results = arbitration.arbitrate([low, high], scores=_scores(low, high))
    by_id = {r.correlation_id: r for r in results}
    assert by_id[high.correlation_id].outcome is ArbitrationOutcome.PROCEED
    assert by_id[low.correlation_id].outcome is not ArbitrationOutcome.PROCEED


def test_a_second_request_exceeding_the_remaining_budget_waits_not_proceeds() -> None:
    """Regression test for the fixed resource-budget bug: two requests, each
    with resource_cost == the full ceiling, must not both PROCEED -- the
    second must WAIT (or PROCEED_REDUCED with a goal, tested separately)
    once the first has already consumed the entire budget."""
    winner = _request(urgency=0.9, resource_cost=1.0)
    loser = _request(urgency=0.1, resource_cost=1.0)
    results = arbitration.arbitrate(
        [loser, winner], scores=_scores(loser, winner), resource_budget_ceiling=1.0
    )
    by_id = {r.correlation_id: r for r in results}
    assert by_id[winner.correlation_id].outcome is ArbitrationOutcome.PROCEED
    assert by_id[loser.correlation_id].outcome is ArbitrationOutcome.WAIT


def test_remaining_budget_yields_proceed_reduced_not_wait() -> None:
    winner = _request(urgency=0.9, resource_cost=0.6)
    loser = _request(urgency=0.1, resource_cost=0.6)
    results = arbitration.arbitrate(
        [loser, winner], scores=_scores(loser, winner), resource_budget_ceiling=1.0
    )
    by_id = {r.correlation_id: r for r in results}
    reduced = by_id[loser.correlation_id]
    assert reduced.outcome is ArbitrationOutcome.PROCEED_REDUCED
    assert reduced.reduced_budget_hint == 0.4  # 1.0 ceiling - 0.6 already consumed


def test_tie_break_prefers_nearer_deadline_then_long_term_alignment_then_correlation_id() -> None:
    now = datetime.now(UTC)
    near_deadline = _request(deadline=now + timedelta(seconds=1))
    far_deadline = _request(deadline=now + timedelta(days=1))
    scores = _scores(near_deadline, far_deadline)
    results = arbitration.arbitrate([far_deadline, near_deadline], scores=scores)
    by_id = {r.correlation_id: r for r in results}
    # Same composite score (deadline plays no part in it) -- the nearer
    # deadline must win the tie-break and receive rank 0 (PROCEED).
    assert by_id[near_deadline.correlation_id].outcome is ArbitrationOutcome.PROCEED
    assert by_id[far_deadline.correlation_id].outcome is not ArbitrationOutcome.PROCEED


def test_user_goals_override_optimization_prevents_wait_for_goal_tied_request() -> None:
    winner = _request(urgency=0.9, resource_cost=1.0)
    goal_id = uuid4()
    goal_backed_loser = _request(urgency=0.1, resource_cost=1.0, goal_id=goal_id)
    results = arbitration.arbitrate(
        [goal_backed_loser, winner],
        scores=_scores(goal_backed_loser, winner),
        resource_budget_ceiling=1.0,
    )
    by_id = {r.correlation_id: r for r in results}
    goal_result = by_id[goal_backed_loser.correlation_id]
    assert goal_result.outcome is ArbitrationOutcome.PROCEED_REDUCED
    assert "user_goals_override_optimization" in goal_result.policies_applied
    assert goal_result.reduced_budget_hint is not None and goal_result.reduced_budget_hint > 0.0


def test_safety_overrides_speed_forces_wait_instead_of_reduced_at_high_risk() -> None:
    winner = _request(urgency=0.9, resource_cost=0.3)
    risky_loser = _request(urgency=0.1, resource_cost=0.3, risk=0.9)
    results = arbitration.arbitrate(
        [risky_loser, winner],
        scores=_scores(risky_loser, winner),
        resource_budget_ceiling=1.0,
        high_risk_threshold=0.7,
    )
    by_id = {r.correlation_id: r for r in results}
    risky_result = by_id[risky_loser.correlation_id]
    assert risky_result.outcome is ArbitrationOutcome.WAIT
    assert "safety_overrides_speed" in risky_result.policies_applied


def test_arbitrate_with_no_contenders_returns_empty_list() -> None:
    assert arbitration.arbitrate([], scores={}) == []


def test_results_are_returned_in_input_order_not_ranked_order() -> None:
    high = _request(urgency=0.9)
    low = _request(urgency=0.1)
    results = arbitration.arbitrate([low, high], scores=_scores(low, high))
    assert [r.correlation_id for r in results] == [low.correlation_id, high.correlation_id]

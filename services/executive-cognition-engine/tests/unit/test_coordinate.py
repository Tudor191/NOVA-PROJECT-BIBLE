"""`domain.coordinate.arbitrate_request` (docs/design/phase-2c/
00-executive-cognition-engine.md §3, §4) -- the top-level orchestration
tying scoring, arbitration, goal correlation, and trace assembly together.
Covers the caller-supplied `goal_tier` fix (long_term_alignment must be
non-zero even though `GoalsPort` always returns `[]`) and the
`executive.decision.completed`/`.failed` outbox-subject selection.
"""

from __future__ import annotations

from uuid import uuid4

from nova_executive_cognition_engine.domain.coordinate import arbitrate_request
from nova_executive_cognition_engine.domain.models import ArbitrationOutcome, ExecutiveRequest

from tests.fakes.ports import FakeGoalsPort
from tests.fakes.repository import FakeExecutiveRepository


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


async def test_arbitrate_request_records_the_primary_request() -> None:
    repository = FakeExecutiveRepository()
    request = _request()
    await arbitrate_request(
        request, other_contenders=[], goals_port=FakeGoalsPort(), repository=repository
    )
    assert request.correlation_id in repository.requests


async def test_arbitrate_request_persists_a_trace_via_finalize_decision() -> None:
    repository = FakeExecutiveRepository()
    request = _request()
    _, trace = await arbitrate_request(
        request, other_contenders=[], goals_port=FakeGoalsPort(), repository=repository
    )
    assert trace.id in repository.decisions
    assert trace.outcome is ArbitrationOutcome.PROCEED


async def test_caller_supplied_goal_tier_produces_nonzero_long_term_alignment() -> None:
    """Regression test for the fix in domain/coordinate.py's `_score_all`:
    GoalsPort always returns `[]` (Planning Engine doesn't exist), so
    without honoring a caller-supplied `goal_tier` directly on the request,
    `long_term_alignment` would be permanently `0.0` in the real system,
    silently defeating ADR-029."""
    repository = FakeExecutiveRepository()
    request = _request(goal_id=uuid4(), goal_tier="established")
    result, _ = await arbitrate_request(
        request, other_contenders=[], goals_port=FakeGoalsPort(goals=[]), repository=repository
    )
    assert result.priority_score.long_term_alignment > 0.0


async def test_no_goal_tier_and_empty_goals_port_yields_zero_alignment() -> None:
    repository = FakeExecutiveRepository()
    request = _request()
    result, _ = await arbitrate_request(
        request, other_contenders=[], goals_port=FakeGoalsPort(goals=[]), repository=repository
    )
    assert result.priority_score.long_term_alignment == 0.0


async def test_arbitrate_request_ranks_against_other_contenders() -> None:
    repository = FakeExecutiveRepository()
    winner = _request(urgency=0.9, resource_cost=1.0)
    loser = _request(urgency=0.1, resource_cost=1.0)
    result, trace = await arbitrate_request(
        loser,
        other_contenders=[winner],
        goals_port=FakeGoalsPort(),
        repository=repository,
        resource_budget_ceiling=1.0,
    )
    assert result.outcome is ArbitrationOutcome.WAIT
    assert trace.winner_correlation_id == winner.correlation_id
    assert loser.correlation_id in trace.rejected_reasons


async def test_arbitrate_request_uses_user_id_from_the_request_not_a_separate_parameter() -> None:
    repository = FakeExecutiveRepository()
    goals_port = FakeGoalsPort()
    request = _request()
    await arbitrate_request(
        request, other_contenders=[], goals_port=goals_port, repository=repository
    )
    assert goals_port.calls == [request.user_id]

"""`domain.contender_registry.ContenderRegistry` (docs/design/phase-2c/
00-executive-cognition-engine.md §4's implementation amendment) -- the
bounded, in-process mechanism behind "rank against other in-flight requests"
(§3). Covers registration, TTL eviction, the max-entries cap, and `resolve`.
"""

from __future__ import annotations

from uuid import uuid4

from nova_executive_cognition_engine.domain.contender_registry import ContenderRegistry
from nova_executive_cognition_engine.domain.models import ExecutiveRequest


def _request() -> ExecutiveRequest:
    return ExecutiveRequest(
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


def test_first_request_sees_no_contenders() -> None:
    registry = ContenderRegistry()
    assert registry.contenders_for(_request()) == []


def test_second_request_sees_the_first_as_a_contender() -> None:
    registry = ContenderRegistry()
    first = _request()
    registry.contenders_for(first)
    others = registry.contenders_for(_request())
    assert [r.correlation_id for r in others] == [first.correlation_id]


def test_a_request_never_sees_itself_as_its_own_contender() -> None:
    registry = ContenderRegistry()
    request = _request()
    registry.contenders_for(request)
    others = registry.contenders_for(request)
    assert request.correlation_id not in [r.correlation_id for r in others]


def test_resolve_removes_a_request_from_future_contender_lists() -> None:
    registry = ContenderRegistry()
    first = _request()
    registry.contenders_for(first)
    registry.resolve(first.correlation_id)
    others = registry.contenders_for(_request())
    assert others == []


def test_resolve_is_a_no_op_for_an_unknown_correlation_id() -> None:
    registry = ContenderRegistry()
    registry.resolve(uuid4())  # must not raise


def test_ttl_expiry_evicts_stale_entries() -> None:
    registry = ContenderRegistry(ttl_seconds=-1.0)  # already expired the instant it's registered
    registry.contenders_for(_request())
    others = registry.contenders_for(_request())
    assert others == []


def test_max_entries_caps_registry_size() -> None:
    registry = ContenderRegistry(max_entries=2)
    for _ in range(5):
        registry.contenders_for(_request())
    others = registry.contenders_for(_request())
    assert len(others) <= 2

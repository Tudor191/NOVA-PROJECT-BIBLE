from uuid import uuid4

import pytest
from nova_ai_model_orchestration_engine.domain import fallback
from nova_ai_model_orchestration_engine.domain.models import ScoredCandidate


def _candidate(model_id=None, score=0.5) -> ScoredCandidate:  # type: ignore[no-untyped-def]
    return ScoredCandidate(
        model_id=model_id or uuid4(),
        capability_score=score,
        cost_score=score,
        latency_score=score,
        historical_success_rate=None,
        composite_score=score,
    )


def test_next_candidate_returns_first_untried() -> None:
    a, b = _candidate(), _candidate()
    result = fallback.next_candidate([a, b], already_tried=[])
    assert result is a


def test_next_candidate_skips_already_tried() -> None:
    a, b = _candidate(), _candidate()
    result = fallback.next_candidate([a, b], already_tried=[a])
    assert result is b


def test_fallback_exhausted_when_all_tried() -> None:
    a, b = _candidate(), _candidate()
    with pytest.raises(fallback.FallbackExhaustedError):
        fallback.next_candidate([a, b], already_tried=[a, b])

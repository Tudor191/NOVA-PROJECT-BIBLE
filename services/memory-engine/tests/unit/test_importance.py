import pytest
from nova_memory_engine.domain.importance import compute_importance, recency_decay


def _score(**overrides: object) -> float:
    defaults: dict[str, object] = {
        "access_count": 5,
        "access_count_p95": 20,
        "days_since_last_access": 3.0,
        "is_active_project": True,
        "user_feedback_score": 0.0,
        "confidence": 0.7,
    }
    defaults.update(overrides)
    return compute_importance(**defaults)  # type: ignore[arg-type]


def test_score_is_bounded_zero_to_one() -> None:
    assert 0.0 <= _score() <= 1.0
    assert 0.0 <= _score(access_count=100_000, confidence=1.0, user_feedback_score=1.0) <= 1.0
    assert 0.0 <= _score(access_count=0, confidence=0.0, user_feedback_score=-1.0) <= 1.0


def test_more_frequent_access_never_decreases_score() -> None:
    low = _score(access_count=1)
    high = _score(access_count=15)
    assert high >= low


def test_more_recent_access_never_decreases_score() -> None:
    stale = _score(days_since_last_access=60.0)
    fresh = _score(days_since_last_access=1.0)
    assert fresh >= stale


def test_active_project_scores_at_least_as_high_as_inactive() -> None:
    inactive = _score(is_active_project=False)
    active = _score(is_active_project=True)
    assert active >= inactive


def test_positive_feedback_never_decreases_score() -> None:
    neutral = _score(user_feedback_score=0.0)
    positive = _score(user_feedback_score=1.0)
    assert positive >= neutral


def test_negative_feedback_never_increases_score() -> None:
    neutral = _score(user_feedback_score=0.0)
    negative = _score(user_feedback_score=-1.0)
    assert negative <= neutral


def test_higher_confidence_never_decreases_score() -> None:
    low_confidence = _score(confidence=0.1)
    high_confidence = _score(confidence=0.9)
    assert high_confidence >= low_confidence


def test_missing_confidence_treated_as_zero_contribution() -> None:
    with_none = _score(confidence=None)
    with_zero = _score(confidence=0.0)
    assert with_none == with_zero


def test_zero_p95_does_not_divide_by_zero() -> None:
    # A brand-new user with no access history yet -- callers pass p95=1 per this
    # function's own docstring, but 0 must not crash either.
    assert 0.0 <= _score(access_count_p95=0) <= 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"access_count": -1},
        {"days_since_last_access": -1.0},
        {"user_feedback_score": 1.5},
        {"user_feedback_score": -1.5},
        {"confidence": 1.5},
        {"confidence": -0.1},
    ],
)
def test_invalid_inputs_raise(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _score(**kwargs)


def test_recency_decay_is_one_at_zero_days() -> None:
    assert recency_decay(0.0) == pytest.approx(1.0)


def test_recency_decay_decreases_with_time() -> None:
    assert recency_decay(30.0) < recency_decay(1.0)


def test_recency_decay_rejects_negative_days() -> None:
    with pytest.raises(ValueError):
        recency_decay(-1.0)

"""Trust Engine, and **negative controls 3 and 4** (TDD §16).

Control 3 -- *coercing `TrustMetric.correction_frequency` `None` -> `0.0` must
fail the suite*.
Control 4 -- *making an absent trust score satisfy a threshold must fail*.

Both guard the same mistake in two places: `None` means *"no evidence"*, and
the dangerous flattening is to `0.0` corrections, which reads as **perfect**
trust -- the exactly-inverted error.
"""

from __future__ import annotations

import math
from uuid import uuid4

import pytest
from nova_autonomy_engine.domain.models import (
    ExecutionOutcomeSummary,
    PermissionCategory,
    TrustInputStatus,
    TrustMetricSnapshot,
)
from nova_autonomy_engine.domain.trust import (
    compute_trust_score,
    conversational_component,
    satisfies_threshold,
)

USER = uuid4()
CATEGORY = PermissionCategory.RECOMMEND


def _score(**kwargs: object) -> object:
    return compute_trust_score(user_id=USER, category=CATEGORY, **kwargs)  # type: ignore[arg-type]


# --- Negative control 3 ------------------------------------------------------
def test_control_3_absent_correction_frequency_yields_no_score_not_zero() -> None:
    """**Negative control 3.** 2D-D: *"'no data yet' is not the same claim as
    'measured zero corrections'"*. Coercing to `0.0` would produce a score of
    `1.0` -- perfect trust from no evidence."""
    assert conversational_component(None) is None

    result = compute_trust_score(
        user_id=USER,
        category=CATEGORY,
        conversational=TrustMetricSnapshot(correction_frequency=None, window_session_count=0),
    )
    assert result.score is None
    assert result.input_status is TrustInputStatus.NO_DATA


def test_control_3_measured_zero_corrections_is_a_different_answer() -> None:
    """The other half of control 3: a *measured* zero must still produce a real
    score, or the two states would be conflated in the safe-looking
    direction."""
    result = compute_trust_score(
        user_id=USER,
        category=CATEGORY,
        conversational=TrustMetricSnapshot(correction_frequency=0.0, window_session_count=12),
    )
    assert result.score == 1.0
    assert result.input_status is TrustInputStatus.AVAILABLE
    assert result.evidence_count == 12


# --- Negative control 4 ------------------------------------------------------
@pytest.mark.parametrize("threshold", [0.0, 0.1, 0.5, 0.9, 1.0])
def test_control_4_an_unknown_score_never_satisfies_any_threshold(threshold: float) -> None:
    """**Negative control 4**, including `threshold=0.0` -- the case a naive
    `score or 0.0 >= threshold` would wrongly pass."""
    assert satisfies_threshold(None, threshold) is False


def test_a_known_score_is_compared_normally() -> None:
    assert satisfies_threshold(0.5, 0.5) is True
    assert satisfies_threshold(0.49, 0.5) is False


def test_the_conversational_map_is_bounded_and_monotone_decreasing() -> None:
    """More corrections per session must never mean more trust."""
    frequencies = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 10.0, 1000.0]
    scores = [conversational_component(f) for f in frequencies]
    assert all(s is not None for s in scores)
    values = [s for s in scores if s is not None]
    assert values == sorted(values, reverse=True)
    assert all(0.0 < value <= 1.0 for value in values)
    assert values[0] == 1.0
    assert math.isclose(conversational_component(1.0) or 0.0, 0.5)


def test_a_negative_correction_frequency_is_rejected_not_clamped() -> None:
    """It cannot occur (a count over a positive count), and silently accepting
    it would produce a score above `1.0`."""
    with pytest.raises(ValueError, match="non-negative"):
        conversational_component(-0.1)


def test_an_unavailable_source_is_distinguishable_from_no_data() -> None:
    """TDD §16 control 12's precondition: both produce `score=None`, but
    reporting the first as the second would report a degraded upstream as an
    empty success."""
    unavailable = compute_trust_score(
        user_id=USER,
        category=CATEGORY,
        conversational=None,
        status=TrustInputStatus.UNAVAILABLE,
        detail="digital-twin-engine exposes no read surface",
    )
    no_data = compute_trust_score(user_id=USER, category=CATEGORY, conversational=None)

    assert unavailable.score is None
    assert no_data.score is None
    assert unavailable.input_status is TrustInputStatus.UNAVAILABLE
    assert no_data.input_status is TrustInputStatus.NO_DATA
    assert unavailable.detail is not None
    assert unavailable.input_status != no_data.input_status


def test_the_reserved_2d_d_acceptance_rates_are_carried_never_computed() -> None:
    """TDD §5.1 item 2: both are reserved and always `None` in 2D-D. Computing
    them here would relocate another engine's deferred work."""
    snapshot = TrustMetricSnapshot(correction_frequency=0.5, window_session_count=4)
    assert snapshot.clarification_acceptance_rate is None
    assert snapshot.proactive_suggestion_acceptance_rate is None

    result = compute_trust_score(user_id=USER, category=CATEGORY, conversational=snapshot)
    assert result.conversational is not None
    assert result.conversational.clarification_acceptance_rate is None
    assert result.conversational.proactive_suggestion_acceptance_rate is None


def test_the_execution_input_is_recorded_but_contributes_nothing_in_4d() -> None:
    """Nothing executes at Levels 0-1, so there are no execution outcomes to
    learn from. Inventing a weighting for evidence this milestone cannot
    produce would be fabricating a formula."""
    snapshot = TrustMetricSnapshot(correction_frequency=1.0, window_session_count=8)
    without = compute_trust_score(user_id=USER, category=CATEGORY, conversational=snapshot)
    with_execution = compute_trust_score(
        user_id=USER,
        category=CATEGORY,
        conversational=snapshot,
        execution=ExecutionOutcomeSummary(total=9, succeeded=9, failed=0),
    )
    assert with_execution.score == without.score
    assert with_execution.execution is not None


def test_the_score_is_per_category() -> None:
    """Bible Part 14: *"NOVA maintains a dynamic trust score for every
    category."* Not one global number."""
    snapshot = TrustMetricSnapshot(correction_frequency=0.0, window_session_count=3)
    for category in PermissionCategory:
        result = compute_trust_score(
            user_id=USER, category=category, conversational=snapshot
        )
        assert result.category is category

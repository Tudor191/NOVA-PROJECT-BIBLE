import pytest
from nova_memory_engine.domain import lifecycle
from nova_memory_engine.domain.lifecycle import ExplicitTrigger
from nova_memory_engine.domain.models import LifecycleState as S


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.ACTIVE, S.WEAK),
        (S.ACTIVE, S.SCHEDULED_FOR_DELETION),
        (S.WEAK, S.ACTIVE),
        (S.WEAK, S.ARCHIVED),
        (S.WEAK, S.SCHEDULED_FOR_DELETION),
        (S.ARCHIVED, S.ACTIVE),
        (S.ARCHIVED, S.SCHEDULED_FOR_DELETION),
        (S.SCHEDULED_FOR_DELETION, S.ACTIVE),
        (S.SCHEDULED_FOR_DELETION, S.DELETED),
    ],
)
def test_every_valid_transition_is_accepted(current: S, target: S) -> None:
    assert lifecycle.is_valid_transition(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.ACTIVE, S.ARCHIVED),
        (S.ACTIVE, S.DELETED),
        (S.ACTIVE, S.ACTIVE),
        (S.WEAK, S.WEAK),
        (S.WEAK, S.DELETED),
        (S.ARCHIVED, S.ARCHIVED),
        (S.ARCHIVED, S.WEAK),
        (S.SCHEDULED_FOR_DELETION, S.SCHEDULED_FOR_DELETION),
        (S.SCHEDULED_FOR_DELETION, S.WEAK),
        (S.SCHEDULED_FOR_DELETION, S.ARCHIVED),
        (S.DELETED, S.ACTIVE),
        (S.DELETED, S.DELETED),
    ],
)
def test_every_invalid_transition_is_rejected(current: S, target: S) -> None:
    assert lifecycle.is_valid_transition(current, target) is False


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (S.ACTIVE, S.ACTIVE),
        (S.WEAK, S.ACTIVE),
        (S.ARCHIVED, S.ACTIVE),
        (S.SCHEDULED_FOR_DELETION, S.ACTIVE),
    ],
)
def test_next_state_on_access_reactivates(current: S, expected: S) -> None:
    assert lifecycle.next_state_on_access(current) == expected


def test_next_state_on_access_is_a_no_op_for_deleted() -> None:
    # DELETED is terminal; callers must not invoke this on a truly deleted record,
    # but the function itself must not crash or resurrect one silently.
    assert lifecycle.next_state_on_access(S.DELETED) == S.DELETED


def test_active_to_weak_requires_both_time_and_low_importance() -> None:
    assert (
        lifecycle.next_state_on_idle(
            S.ACTIVE,
            days_since_last_access=lifecycle.WEAK_THRESHOLD_DAYS,
            importance_score=0.1,
            has_active_project_reference=False,
        )
        == S.WEAK
    )
    # Enough time, but importance too high -- stays ACTIVE.
    assert (
        lifecycle.next_state_on_idle(
            S.ACTIVE,
            days_since_last_access=lifecycle.WEAK_THRESHOLD_DAYS,
            importance_score=0.9,
            has_active_project_reference=False,
        )
        == S.ACTIVE
    )
    # Low importance, but not enough time -- stays ACTIVE.
    assert (
        lifecycle.next_state_on_idle(
            S.ACTIVE,
            days_since_last_access=1.0,
            importance_score=0.1,
            has_active_project_reference=False,
        )
        == S.ACTIVE
    )


def test_weak_to_archived_requires_time_and_no_active_project() -> None:
    assert (
        lifecycle.next_state_on_idle(
            S.WEAK,
            days_since_last_access=lifecycle.ARCHIVE_THRESHOLD_DAYS,
            importance_score=0.0,
            has_active_project_reference=False,
        )
        == S.ARCHIVED
    )
    # Active project reference blocks archival even after the threshold.
    assert (
        lifecycle.next_state_on_idle(
            S.WEAK,
            days_since_last_access=lifecycle.ARCHIVE_THRESHOLD_DAYS,
            importance_score=0.0,
            has_active_project_reference=True,
        )
        == S.WEAK
    )


def test_idle_never_produces_scheduled_for_deletion() -> None:
    """The passive path must never reach SCHEDULED_FOR_DELETION -- Part 3's
    "never disappear immediately" guarantee depends on this."""
    for current in (S.ACTIVE, S.WEAK, S.ARCHIVED):
        result = lifecycle.next_state_on_idle(
            current,
            days_since_last_access=10_000.0,
            importance_score=0.0,
            has_active_project_reference=False,
        )
        assert result != S.SCHEDULED_FOR_DELETION


@pytest.mark.parametrize("trigger", list(ExplicitTrigger))
@pytest.mark.parametrize("current", [S.ACTIVE, S.WEAK, S.ARCHIVED])
def test_explicit_trigger_schedules_deletion_from_any_non_terminal_state(
    current: S, trigger: ExplicitTrigger
) -> None:
    assert lifecycle.next_state_on_explicit_trigger(current, trigger) == S.SCHEDULED_FOR_DELETION


def test_explicit_trigger_is_idempotent_once_scheduled() -> None:
    result = lifecycle.next_state_on_explicit_trigger(
        S.SCHEDULED_FOR_DELETION, ExplicitTrigger.USER_DELETE_REQUEST
    )
    assert result == S.SCHEDULED_FOR_DELETION


def test_explicit_trigger_never_resurrects_deleted() -> None:
    result = lifecycle.next_state_on_explicit_trigger(
        S.DELETED, ExplicitTrigger.USER_DELETE_REQUEST
    )
    assert result == S.DELETED


def test_grace_period_elapsed_deletes() -> None:
    result = lifecycle.next_state_on_grace_period_check(
        S.SCHEDULED_FOR_DELETION, days_since_scheduled=lifecycle.DEFAULT_GRACE_PERIOD_DAYS
    )
    assert result == S.DELETED


def test_grace_period_not_yet_elapsed_keeps_scheduled() -> None:
    result = lifecycle.next_state_on_grace_period_check(
        S.SCHEDULED_FOR_DELETION, days_since_scheduled=1.0
    )
    assert result == S.SCHEDULED_FOR_DELETION


def test_grace_period_check_only_applies_to_scheduled_state() -> None:
    result = lifecycle.next_state_on_grace_period_check(S.ACTIVE, days_since_scheduled=10_000.0)
    assert result == S.ACTIVE

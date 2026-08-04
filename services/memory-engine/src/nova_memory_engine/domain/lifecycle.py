"""The forgetting state machine -- docs/design/phase-1/01-memory-engine.md §6.

Pure functions only: this module decides what the *next* state would be given the
current state and some facts; it never decides *when* to check (that is
`workers/consolidation_worker.py`'s schedule) and never performs I/O.

Per Part 3's explicit caution ("forgotten memories should never disappear
immediately... this prevents accidental information loss"),
`ARCHIVED -> SCHEDULED_FOR_DELETION` is never reached by the passive, time-based
path (`next_state_on_idle`) -- only by `next_state_on_explicit_trigger`.
"""

from __future__ import annotations

from enum import StrEnum

from nova_memory_engine.domain.models import LifecycleState

__all__ = [
    "ExplicitTrigger",
    "WEAK_THRESHOLD_DAYS",
    "WEAK_THRESHOLD_IMPORTANCE",
    "ARCHIVE_THRESHOLD_DAYS",
    "DEFAULT_GRACE_PERIOD_DAYS",
    "is_valid_transition",
    "next_state_on_access",
    "next_state_on_idle",
    "next_state_on_explicit_trigger",
    "next_state_on_grace_period_check",
]

WEAK_THRESHOLD_DAYS = 30.0
WEAK_THRESHOLD_IMPORTANCE = 0.3
ARCHIVE_THRESHOLD_DAYS = 90.0
DEFAULT_GRACE_PERIOD_DAYS = 30.0

_S = LifecycleState

# The complete, closed set of valid transitions -- the union of what the passive
# (`next_state_on_idle`) and explicit-trigger (`next_state_on_explicit_trigger`,
# `next_state_on_access`) paths can produce. `is_valid_transition` is the single
# source of truth every other function's output is checked against in tests.
_VALID_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    _S.ACTIVE: frozenset({_S.WEAK, _S.SCHEDULED_FOR_DELETION}),
    _S.WEAK: frozenset({_S.ACTIVE, _S.ARCHIVED, _S.SCHEDULED_FOR_DELETION}),
    _S.ARCHIVED: frozenset({_S.ACTIVE, _S.SCHEDULED_FOR_DELETION}),
    _S.SCHEDULED_FOR_DELETION: frozenset({_S.ACTIVE, _S.DELETED}),
    _S.DELETED: frozenset(),
}


class ExplicitTrigger(StrEnum):
    """The only three ways `ARCHIVED -> SCHEDULED_FOR_DELETION` (or, per the API's
    "delete is never immediate" contract, `ACTIVE`/`WEAK` -> `SCHEDULED_FOR_DELETION`)
    may happen in Phase 1."""

    DUPLICATE_MERGED = "duplicate_merged"
    USER_DELETE_REQUEST = "user_delete_request"
    CONTRADICTION_SUPERSEDED = "contradiction_superseded"


def is_valid_transition(current: LifecycleState, target: LifecycleState) -> bool:
    return target in _VALID_TRANSITIONS.get(current, frozenset())


def next_state_on_access(current: LifecycleState) -> LifecycleState:
    """Any access reactivates `WEAK`/`ARCHIVED`/`SCHEDULED_FOR_DELETION` (within its
    grace period -- the caller is responsible for not calling this on a truly
    `DELETED` record) back to `ACTIVE`. `ACTIVE` accessed stays `ACTIVE`."""
    if current in (_S.WEAK, _S.ARCHIVED, _S.SCHEDULED_FOR_DELETION):
        return _S.ACTIVE
    return current


def next_state_on_idle(
    current: LifecycleState,
    *,
    days_since_last_access: float,
    importance_score: float,
    has_active_project_reference: bool,
) -> LifecycleState:
    """Passive, time-based transitions only -- `ACTIVE -> WEAK` and
    `WEAK -> ARCHIVED`. Never produces `SCHEDULED_FOR_DELETION`; see module
    docstring."""
    if (
        current == _S.ACTIVE
        and days_since_last_access >= WEAK_THRESHOLD_DAYS
        and importance_score < WEAK_THRESHOLD_IMPORTANCE
    ):
        return _S.WEAK
    if (
        current == _S.WEAK
        and days_since_last_access >= ARCHIVE_THRESHOLD_DAYS
        and not has_active_project_reference
    ):
        return _S.ARCHIVED
    return current


def next_state_on_explicit_trigger(
    current: LifecycleState, trigger: ExplicitTrigger  # noqa: ARG001 -- kept for call-site clarity/audit trail
) -> LifecycleState:
    """Any of the three explicit triggers moves a non-terminal, not-yet-scheduled
    record straight to `SCHEDULED_FOR_DELETION` -- deliberately trigger-agnostic in
    its *output* (the trigger only matters for the audit log, not the destination
    state), since Phase 1 has exactly one "about to be deleted" state regardless of
    why."""
    if current in (_S.SCHEDULED_FOR_DELETION, _S.DELETED):
        return current
    return _S.SCHEDULED_FOR_DELETION


def next_state_on_grace_period_check(
    current: LifecycleState,
    *,
    days_since_scheduled: float,
    grace_period_days: float = DEFAULT_GRACE_PERIOD_DAYS,
) -> LifecycleState:
    """The only path to `DELETED`: `SCHEDULED_FOR_DELETION`, untouched, for
    `grace_period_days`."""
    if current == _S.SCHEDULED_FOR_DELETION and days_since_scheduled >= grace_period_days:
        return _S.DELETED
    return current

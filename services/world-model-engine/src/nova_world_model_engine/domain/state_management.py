"""Object state transitions -- docs/design/phase-1/03-world-model-engine.md §6.
Pure, table-driven, mirroring Memory Engine's `domain/lifecycle.py` pattern. World
Model has no *forgetting* lifecycle (that's Memory's job) -- this table describes
transitions between states of current reality, not decay toward deletion.

Only the edges explicitly drawn in §6's state diagram are implemented.
`WAITING` and `LEARNING` have no outgoing edge in that diagram -- rather than
invent a plausible-sounding one (e.g. "Waiting -> Executing once unblocked"),
this is left as a documented gap: a real signal for "dependency resolved" isn't
defined in Phase 1's event surface, so guessing the transition trigger would be
speculative behavior, not implementation.
"""

from __future__ import annotations

from typing import Literal

from nova_world_model_engine.domain.models import ObjectState

_VALID_TRANSITIONS: dict[ObjectState, frozenset[ObjectState]] = {
    ObjectState.UNKNOWN: frozenset({ObjectState.ACTIVE}),
    ObjectState.ACTIVE: frozenset(
        {ObjectState.IDLE, ObjectState.EXECUTING, ObjectState.LEARNING}
    ),
    ObjectState.IDLE: frozenset({ObjectState.ACTIVE}),
    ObjectState.EXECUTING: frozenset(
        {ObjectState.COMPLETED, ObjectState.FAILED, ObjectState.WAITING}
    ),
    ObjectState.WAITING: frozenset(),  # no outgoing edge in §6 -- documented gap
    ObjectState.LEARNING: frozenset(),  # no outgoing edge in §6 -- documented gap
    ObjectState.COMPLETED: frozenset(),  # terminal
    ObjectState.FAILED: frozenset(),  # terminal
}

ExecutionOutcome = Literal["success", "error", "blocked"]

_EXECUTION_OUTCOME_STATE: dict[ExecutionOutcome, ObjectState] = {
    "success": ObjectState.COMPLETED,
    "error": ObjectState.FAILED,
    "blocked": ObjectState.WAITING,
}


def is_valid_transition(from_state: ObjectState, to_state: ObjectState) -> bool:
    return to_state in _VALID_TRANSITIONS[from_state]


def next_state_on_first_observation(current: ObjectState) -> ObjectState | None:
    """`Unknown -> Active`. Only fires from `UNKNOWN` -- an already-known object
    being observed again is `next_state_on_new_observation`, not this."""
    if current is not ObjectState.UNKNOWN:
        return None
    return ObjectState.ACTIVE if is_valid_transition(current, ObjectState.ACTIVE) else None


def next_state_on_new_observation(current: ObjectState) -> ObjectState | None:
    """`Idle -> Active` on any new observation. A no-op (returns `None`, meaning
    "no transition") for every other state -- an `ACTIVE` object receiving
    another observation just stays `ACTIVE`."""
    if current is not ObjectState.IDLE:
        return None
    return ObjectState.ACTIVE if is_valid_transition(current, ObjectState.ACTIVE) else None


def next_state_on_idle_timeout(current: ObjectState) -> ObjectState | None:
    """`Active -> Idle` after no related perception events for N minutes
    (a per-object-type threshold the caller, `workers/`, is responsible for
    applying -- this function only knows the *state* transition, not timing)."""
    if current is not ObjectState.ACTIVE:
        return None
    return ObjectState.IDLE if is_valid_transition(current, ObjectState.IDLE) else None


def next_state_on_execution_start(current: ObjectState) -> ObjectState | None:
    """`Active -> Executing`, for task/agent-related objects only -- the caller
    decides whether an object is execution-capable; this function only encodes
    the state-machine edge."""
    if current is not ObjectState.ACTIVE:
        return None
    return ObjectState.EXECUTING if is_valid_transition(current, ObjectState.EXECUTING) else None


def next_state_on_execution_result(
    current: ObjectState, *, outcome: ExecutionOutcome
) -> ObjectState | None:
    """`Executing -> Completed | Failed | Waiting`."""
    if current is not ObjectState.EXECUTING:
        return None
    target = _EXECUTION_OUTCOME_STATE[outcome]
    return target if is_valid_transition(current, target) else None


def next_state_on_exploration_start(current: ObjectState) -> ObjectState | None:
    """`Active -> Learning` (object under active exploration, e.g. a new
    technology being researched)."""
    if current is not ObjectState.ACTIVE:
        return None
    return ObjectState.LEARNING if is_valid_transition(current, ObjectState.LEARNING) else None

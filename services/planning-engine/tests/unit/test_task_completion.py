"""Unit tests for `domain/task_completion.py::resolve_transitions` -- the
full `agent_os.task.completed` TaskNode-lifecycle decision (TDD 3E §4/§12,
TDD 3B §6.1), including the explicit Phase 3 decision that
`outcome="failure"` is terminal rather than redispatched.

Pure functions only: no repository, no Event Bus, no `TaskGraph`
persistence. `events/task_completed_handler.py`'s own integration tests
cover the wiring; these cover the decision.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskNode, TaskNodeStatus
from nova_planning_engine.domain.task_completion import (
    OUTCOME_TRANSITIONS,
    TERMINAL_STATUSES,
    resolve_transitions,
)


def _node(**overrides: object) -> TaskNode:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "objective": "Add a health-check endpoint",
        "depends_on": [],
        "assigned_agent_category": "coding",
        "estimated_effort": Estimate(effort_hours=2.0, confidence=0.8),
        "risk": RiskLevel.LOW,
        "status": "running",
    }
    defaults.update(overrides)
    return TaskNode(**defaults)  # type: ignore[arg-type]


def _transitions_for(outcome: str, node: TaskNode, *extra: TaskNode) -> list[tuple[UUID, str]]:
    return [
        (node_id, status)
        for node_id, status in resolve_transitions(
            outcome=outcome, task_node_id=node.id, nodes=[node, *extra]
        )
    ]


# --- The four recognised outcomes -------------------------------------------


def test_success_marks_the_node_completed() -> None:
    node = _node()
    assert _transitions_for("success", node) == [(node.id, "completed")]


def test_interrupted_resets_the_node_to_ready() -> None:
    """TDD 3E §4/§12's Kernel-restart-reconciliation path, unchanged from the
    restart-resume slice: the instance died with the old Kernel process, no
    `AgentResult` was ever produced, the assignment must not be lost."""
    node = _node()
    assert _transitions_for("interrupted", node) == [(node.id, "ready")]


def test_needs_revision_resets_the_node_to_ready() -> None:
    """A `rejected` peer review is an explicit request for another execution
    round (`agent-os/kernel`'s Scheduler publishes this outcome only for
    that verdict), not an instance fault."""
    node = _node()
    assert _transitions_for("needs_revision", node) == [(node.id, "ready")]


def test_failure_marks_the_node_terminally_failed() -> None:
    """The approved Phase 3 decision (Option B). TDD 3E §12 does not define
    post-retry failure semantics; by the time this outcome is published the
    Kernel has already run the Supervisor restart path and its bounded
    retry, so the node is terminal rather than redispatched. See
    `domain/task_completion.py`'s own docstring for the full record."""
    node = _node()
    assert _transitions_for("failure", node) == [(node.id, "failed")]


def test_failure_is_terminal_and_never_enters_an_unbounded_redispatch_loop() -> None:
    """The concrete hazard Option B exists to prevent, proven directly: a
    deterministically-failing node fails, is marked `"failed"`, and every
    subsequent `"failure"` for the same node yields NO further transition --
    so the Scheduler is never handed it again. Under the previous
    `"failure"` -> `"ready"` rule this loop had no stopping condition
    anywhere in the documents."""
    node = _node(status="running")

    first = _transitions_for("failure", node)
    assert first == [(node.id, "failed")]

    # The node now carries the status that first round produced. Replay the
    # same deterministic failure as many times as the Kernel could ever
    # publish it: no transition is ever produced again, so no republish is
    # enqueued and no redispatch can occur.
    failed_node = node.model_copy(update={"status": "failed"})
    for _ in range(5):
        assert _transitions_for("failure", failed_node) == []
        assert _transitions_for("interrupted", failed_node) == []
        assert _transitions_for("needs_revision", failed_node) == []
        assert _transitions_for("success", failed_node) == []


# --- Dependent promotion ----------------------------------------------------


def test_success_promotes_a_dependent_whose_only_dependency_just_completed() -> None:
    first = _node(objective="write the endpoint")
    second = _node(objective="test it", depends_on=[first.id], status="pending")

    assert _transitions_for("success", first, second) == [
        (first.id, "completed"),
        (second.id, "ready"),
    ]


def test_success_does_not_promote_a_dependent_with_an_outstanding_dependency() -> None:
    first = _node(objective="write the endpoint")
    other = _node(objective="write the docs", status="running")
    third = _node(objective="review both", depends_on=[first.id, other.id], status="pending")

    assert _transitions_for("success", first, other, third) == [(first.id, "completed")]


def test_success_promotes_a_dependent_once_its_last_dependency_completes() -> None:
    first = _node(objective="write the endpoint", status="completed")
    other = _node(objective="write the docs")
    third = _node(objective="review both", depends_on=[first.id, other.id], status="pending")

    assert _transitions_for("success", other, first, third) == [
        (other.id, "completed"),
        (third.id, "ready"),
    ]


def test_success_promotes_several_dependents_at_once() -> None:
    root = _node(objective="scaffold")
    left = _node(objective="left", depends_on=[root.id], status="pending")
    right = _node(objective="right", depends_on=[root.id], status="pending")

    transitions = _transitions_for("success", root, left, right)
    assert transitions[0] == (root.id, "completed")
    assert set(transitions[1:]) == {(left.id, "ready"), (right.id, "ready")}


def test_a_non_success_outcome_never_promotes_dependents() -> None:
    first = _node()
    second = _node(depends_on=[first.id], status="pending")

    for outcome in ("failure", "interrupted", "needs_revision"):
        transitions = _transitions_for(outcome, first, second)
        assert [node_id for node_id, _status in transitions] == [first.id]


def test_a_dependent_of_a_failed_node_is_never_promoted() -> None:
    """A node whose dependency ended `"failed"` stays `"pending"` -- it is
    not runnable, and nothing in this module invents a "skip the failed
    dependency" recovery path."""
    first = _node(status="failed")
    second = _node(depends_on=[first.id], status="pending")

    assert _transitions_for("success", second) == [(second.id, "completed")]
    assert (
        resolve_transitions(outcome="failure", task_node_id=first.id, nodes=[first, second]) == []
    )


# --- Idempotency / redelivery guards ----------------------------------------


@pytest.mark.parametrize("outcome", ["success", "failure", "interrupted", "needs_revision"])
def test_an_already_completed_node_is_never_transitioned(outcome: str) -> None:
    """NATS JetStream is at-least-once: a redelivered event must never undo
    finished work or re-dispatch an instance that already ran."""
    node = _node(status="completed")
    assert _transitions_for(outcome, node) == []


@pytest.mark.parametrize("outcome", ["success", "failure", "interrupted", "needs_revision"])
def test_an_already_failed_node_is_never_transitioned(outcome: str) -> None:
    node = _node(status="failed")
    assert _transitions_for(outcome, node) == []


def test_an_unrecognised_outcome_produces_no_transitions() -> None:
    node = _node()
    assert _transitions_for("something-new", node) == []
    assert _transitions_for("", node) == []


def test_a_task_node_id_absent_from_the_graph_produces_no_transitions() -> None:
    node = _node()
    assert resolve_transitions(outcome="success", task_node_id=uuid4(), nodes=[node]) == []


def test_no_transitions_for_an_empty_graph() -> None:
    assert resolve_transitions(outcome="success", task_node_id=uuid4(), nodes=[]) == []


# --- The decision table itself ----------------------------------------------


def test_terminal_statuses_are_exactly_completed_and_failed() -> None:
    assert frozenset({"completed", "failed"}) == TERMINAL_STATUSES


def test_the_outcome_table_matches_the_approved_decision() -> None:
    """Guards the four approved mappings against silent drift -- especially
    `"failure"` -> `"failed"`, which narrows TDD 3E §12 and must not be
    changed back without revisiting that decision."""
    expected: dict[str, TaskNodeStatus] = {
        "success": "completed",
        "failure": "failed",
        "interrupted": "ready",
        "needs_revision": "ready",
    }
    assert expected == OUTCOME_TRANSITIONS

"""Unit tests for `domain/task_completion.py::should_reset_to_ready` -- TDD
3E §4/§12's restart-resume trigger set. Pure function, no repository or
Event Bus involved."""

from __future__ import annotations

from nova_planning_engine.domain.task_completion import (
    RESUME_TRIGGERING_OUTCOMES,
    should_reset_to_ready,
)


def test_resume_triggering_outcomes_is_exactly_interrupted_and_failure() -> None:
    assert {"interrupted", "failure"} == RESUME_TRIGGERING_OUTCOMES


def test_interrupted_outcome_resets_a_ready_node() -> None:
    assert should_reset_to_ready(outcome="interrupted", current_status="ready") is True


def test_interrupted_outcome_resets_a_running_node() -> None:
    assert should_reset_to_ready(outcome="interrupted", current_status="running") is True


def test_interrupted_outcome_resets_a_blocked_node() -> None:
    assert should_reset_to_ready(outcome="interrupted", current_status="blocked") is True


def test_failure_outcome_resets_a_running_node() -> None:
    assert should_reset_to_ready(outcome="failure", current_status="running") is True


def test_success_outcome_never_resets() -> None:
    assert should_reset_to_ready(outcome="success", current_status="running") is False
    assert should_reset_to_ready(outcome="success", current_status="ready") is False


def test_needs_revision_outcome_never_resets() -> None:
    """Peer-review quality signal, not an instance fault (TDD 3E §12) --
    no document describes a revision-loop recovery path, so it is left
    untouched by this restart-resume-only decision function."""
    assert should_reset_to_ready(outcome="needs_revision", current_status="running") is False


def test_an_already_completed_node_is_never_reset_even_on_interrupted() -> None:
    """Preserve completed work, do not duplicate completed agent
    instances -- the one idempotency guard beyond the outcome check."""
    assert should_reset_to_ready(outcome="interrupted", current_status="completed") is False


def test_an_already_completed_node_is_never_reset_even_on_failure() -> None:
    assert should_reset_to_ready(outcome="failure", current_status="completed") is False


def test_an_already_failed_node_can_still_be_reset() -> None:
    """A node already marked `"failed"` (e.g. by a prior, unresolved
    failure) is not `"completed"` -- a fresh interrupted/failure report
    for it still triggers a reset, unlike the `"completed"` guard."""
    assert should_reset_to_ready(outcome="interrupted", current_status="failed") is True

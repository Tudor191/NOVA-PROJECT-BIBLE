from uuid import uuid4

import pytest
from nova_contracts import (
    ConstraintKind,
    ConstraintPayload,
    FailureAction,
    GoalPayload,
    HumanOverrideAppliedPayload,
    OverrideAction,
    ReasoningMode,
    ReasoningOutcome,
    ReasoningProcessCompletedPayload,
    ReasoningProcessFailedPayload,
    ReasoningReplyPayload,
    ReasoningRequestPayload,
    known_subjects,
    validate_payload,
)
from pydantic import ValidationError


def test_all_reasoning_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "reasoning.reason.request",
        "reasoning.reason.reply",
        "reasoning.process.completed",
        "reasoning.process.failed",
        "reasoning.human_override.applied",
    ):
        assert subject in subjects


def test_reasoning_request_defaults_and_schema_version() -> None:
    request = ReasoningRequestPayload(
        objective_text="find the best next action",
        user_id=uuid4(),
        requesting_engine="world-model-engine",
    )
    assert request.reasoning_mode_hint is None
    assert request.reasoning_level_hint is None
    assert request.thinking_mode_hint is None
    assert request.goals == []
    assert request.constraints == []
    assert request.parent_process_id is None
    assert request.prior_nova_utterance is None
    assert request.schema_version == 1


def test_reasoning_request_accepts_prior_nova_utterance() -> None:
    """Phase 2D-D (06-personal-companion.md Sec5.2) -- optional, additive;
    a non-communication-engine caller (e.g. a future Planning Engine) simply
    never sets it, per the default above."""
    request = ReasoningRequestPayload(
        objective_text="actually it's Tuesday, not Wednesday",
        user_id=uuid4(),
        requesting_engine="communication-engine",
        prior_nova_utterance="Your meeting is Wednesday at 3pm.",
    )
    assert request.prior_nova_utterance == "Your meeting is Wednesday at 3pm."


def test_reasoning_request_accepts_goals_and_constraints() -> None:
    request = ReasoningRequestPayload(
        objective_text="plan the week",
        user_id=uuid4(),
        requesting_engine="world-model-engine",
        reasoning_mode_hint=ReasoningMode.STRATEGIC,
        reasoning_level_hint=3,
        goals=[GoalPayload(id=uuid4(), description="stay on budget", priority=0.8)],
        constraints=[
            ConstraintPayload(kind=ConstraintKind.BUDGET, description="under $50", hard=True)
        ],
    )
    assert request.reasoning_mode_hint is ReasoningMode.STRATEGIC
    assert request.goals[0].priority == 0.8
    assert request.constraints[0].kind is ConstraintKind.BUDGET


def test_reasoning_reply_validates_against_registry() -> None:
    validated = validate_payload(
        "reasoning.reason.reply",
        {
            "reasoning_process_id": str(uuid4()),
            "outcome": "decided",
        },
    )
    assert isinstance(validated, ReasoningReplyPayload)
    assert validated.decision_id is None
    assert validated.error is None
    assert validated.outcome is ReasoningOutcome.DECIDED
    assert validated.is_correction is None


def test_reasoning_reply_is_correction_round_trips() -> None:
    """Phase 2D-D Sec5.1 -- `None` (no judgment attempted) is distinct from
    `False` (judged and not a correction); both round-trip explicitly."""
    reply = ReasoningReplyPayload(
        reasoning_process_id=uuid4(), outcome=ReasoningOutcome.DECIDED, is_correction=True
    )
    assert reply.is_correction is True

    reply_false = ReasoningReplyPayload(
        reasoning_process_id=uuid4(), outcome=ReasoningOutcome.DECIDED, is_correction=False
    )
    assert reply_false.is_correction is False


def test_reasoning_process_completed_round_trip() -> None:
    completed = ReasoningProcessCompletedPayload(
        reasoning_process_id=uuid4(),
        correlation_id=uuid4(),
        requesting_engine="world-model-engine",
        user_id=uuid4(),
        reasoning_mode=ReasoningMode.ANALYTICAL,
        reasoning_level=2,
        confidence_score=0.75,
        execution_duration_ms=120.5,
        outcome=ReasoningOutcome.DECIDED,
    )
    assert completed.reasoning_mode is ReasoningMode.ANALYTICAL
    assert completed.schema_version == 1


def test_reasoning_process_failed_carries_stage_and_action() -> None:
    failed = ReasoningProcessFailedPayload(
        reasoning_process_id=uuid4(),
        correlation_id=uuid4(),
        requesting_engine="world-model-engine",
        stage="hypothesis_generating",
        action=FailureAction.RETRIEVE_MORE_KNOWLEDGE,
        reason="no hypotheses cleared the confidence floor",
    )
    assert failed.retry_count == 0
    assert failed.action is FailureAction.RETRIEVE_MORE_KNOWLEDGE


def test_human_override_applied_action_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        HumanOverrideAppliedPayload(
            reasoning_process_id=uuid4(),
            action="not-a-real-action",  # type: ignore[arg-type]
        )

    override = HumanOverrideAppliedPayload(
        reasoning_process_id=uuid4(),
        action=OverrideAction.REDIRECT,
        redirect_alternative_id=uuid4(),
    )
    assert override.action is OverrideAction.REDIRECT


def test_reasoning_mode_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        ReasoningRequestPayload(
            objective_text="x",
            user_id=uuid4(),
            requesting_engine="world-model-engine",
            reasoning_mode_hint="not-a-real-mode",  # type: ignore[arg-type]
        )


def test_reasoning_level_hint_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ReasoningRequestPayload(
            objective_text="x",
            user_id=uuid4(),
            requesting_engine="world-model-engine",
            reasoning_level_hint=5,
        )

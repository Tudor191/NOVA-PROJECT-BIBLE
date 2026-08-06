from uuid import uuid4

import pytest
from nova_contracts import (
    ArbitrationOutcome,
    CognitivePriorityScore,
    ConflictSignals,
    ContenderSummary,
    ExecutiveArbitrateReplyPayload,
    ExecutiveDecisionCompletedPayload,
    ExecutiveDecisionFailedPayload,
    ExecutiveDecisionType,
    ExecutiveHumanOverrideAppliedPayload,
    ExecutiveOutcomeReportPayload,
    ExecutiveOverrideAction,
    ExecutiveRequestPayload,
    GoalTier,
    OutcomeReportResult,
    known_subjects,
    validate_payload,
)
from pydantic import ValidationError


def test_all_executive_cognition_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "executive.arbitrate.request",
        "executive.arbitrate.reply",
        "executive.outcome.report",
        "executive.outcome.report.reply",
        "executive.decision.completed",
        "executive.decision.failed",
        "executive.human_override.applied",
    ):
        assert subject in subjects


def test_executive_request_defaults_and_schema_version() -> None:
    request = ExecutiveRequestPayload(
        requesting_engine="reasoning-engine",
        request_kind="reasoning_process",
        urgency=0.5,
        importance=0.5,
        complexity=0.5,
        risk=0.5,
        learning_value=0.5,
        resource_cost=0.5,
        user_impact=0.5,
    )
    assert request.deadline is None
    assert request.goal_id is None
    assert request.goal_tier is None
    assert request.schema_version == 1


def test_executive_request_accepts_caller_supplied_goal_tier() -> None:
    tier: GoalTier = "established"
    request = ExecutiveRequestPayload(
        requesting_engine="reasoning-engine",
        request_kind="reasoning_process",
        urgency=0.5,
        importance=0.5,
        complexity=0.5,
        risk=0.5,
        learning_value=0.5,
        resource_cost=0.5,
        user_impact=0.5,
        goal_id=uuid4(),
        goal_tier=tier,
    )
    assert request.goal_tier == "established"

    with pytest.raises(ValidationError):
        ExecutiveRequestPayload(
            requesting_engine="reasoning-engine",
            request_kind="reasoning_process",
            urgency=0.5,
            importance=0.5,
            complexity=0.5,
            risk=0.5,
            learning_value=0.5,
            resource_cost=0.5,
            user_impact=0.5,
            goal_tier="not-a-real-tier",  # type: ignore[arg-type]
        )


def test_executive_request_priority_factors_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ExecutiveRequestPayload(
            requesting_engine="reasoning-engine",
            request_kind="reasoning_process",
            urgency=1.5,
            importance=0.5,
            complexity=0.5,
            risk=0.5,
            learning_value=0.5,
            resource_cost=0.5,
            user_impact=0.5,
        )


def test_cognitive_priority_score_carries_eight_factors() -> None:
    score = CognitivePriorityScore(
        urgency=0.8,
        importance=0.7,
        complexity=0.3,
        risk=0.2,
        learning_value=0.4,
        resource_cost=0.1,
        user_impact=0.6,
        long_term_alignment=0.9,
        composite=0.75,
    )
    assert score.long_term_alignment == 0.9


def test_arbitrate_reply_validates_against_registry() -> None:
    validated = validate_payload(
        "executive.arbitrate.reply",
        {
            "correlation_id": str(uuid4()),
            "executive_decision_id": str(uuid4()),
            "outcome": "proceed",
            "priority_score": {
                "urgency": 0.5,
                "importance": 0.5,
                "complexity": 0.5,
                "risk": 0.5,
                "learning_value": 0.5,
                "resource_cost": 0.5,
                "user_impact": 0.5,
                "long_term_alignment": 0.0,
                "composite": 0.5,
            },
        },
    )
    assert isinstance(validated, ExecutiveArbitrateReplyPayload)
    assert validated.outcome is ArbitrationOutcome.PROCEED
    assert validated.retry_after_ms is None
    assert validated.error is None


def test_executive_decision_completed_round_trip() -> None:
    completed = ExecutiveDecisionCompletedPayload(
        executive_decision_id=uuid4(),
        correlation_id=uuid4(),
        decision_type=ExecutiveDecisionType.RESOURCE_ARBITRATION,
        contending_requests=[
            ContenderSummary(
                requesting_engine="reasoning-engine",
                request_kind="reasoning_process",
                correlation_id=uuid4(),
            ),
            ContenderSummary(
                requesting_engine="ai-model-orchestration-engine",
                request_kind="model_generate",
                correlation_id=uuid4(),
            ),
        ],
        outcome=ArbitrationOutcome.PROCEED,
        execution_duration_ms=4.2,
    )
    assert len(completed.contending_requests) == 2
    assert completed.schema_version == 1


def test_executive_decision_failed_carries_a_reason() -> None:
    failed = ExecutiveDecisionFailedPayload(
        correlation_id=uuid4(),
        reason="missing required priority factor: urgency",
    )
    assert failed.reason


def test_human_override_applied_action_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        ExecutiveHumanOverrideAppliedPayload(
            executive_decision_id=uuid4(),
            action="not-a-real-action",  # type: ignore[arg-type]
        )

    override = ExecutiveHumanOverrideAppliedPayload(
        executive_decision_id=uuid4(),
        action=ExecutiveOverrideAction.REDIRECT,
        redirect_outcome=ArbitrationOutcome.WAIT,
    )
    assert override.action is ExecutiveOverrideAction.REDIRECT


def test_human_override_applied_round_trip() -> None:
    applied = ExecutiveHumanOverrideAppliedPayload(
        executive_decision_id=uuid4(),
        action=ExecutiveOverrideAction.CONFIRM,
    )
    assert applied.redirect_outcome is None
    assert applied.schema_version == 1


def test_outcome_report_result_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        ExecutiveOutcomeReportPayload(
            correlation_id=uuid4(),
            outcome="not-a-real-outcome",  # type: ignore[arg-type]
        )

    report = ExecutiveOutcomeReportPayload(
        correlation_id=uuid4(),
        outcome=OutcomeReportResult.SUCCEEDED,
        actual_duration_ms=250.0,
    )
    assert report.outcome is OutcomeReportResult.SUCCEEDED


def test_conflict_signals_never_carries_domain_content_only_labels() -> None:
    signals = ConflictSignals(
        evidence_comparison="side A cited 3 evidence items, side B cited 1",
        confidence_comparison="side A: 0.82, side B: 0.61",
    )
    assert signals.policy_applied is None
    assert signals.user_objective_signal is None
    assert signals.historical_outcome_signal is None

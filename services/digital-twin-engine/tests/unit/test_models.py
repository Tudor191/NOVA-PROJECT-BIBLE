from datetime import UTC, datetime
from uuid import uuid4

from nova_digital_twin_engine.domain.models import (
    CommunicationProfile,
    CompletedSessionEvidence,
    HabitSignal,
    PreferenceEvolutionEntry,
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    ProactiveSuggestion,
    ProactiveSuggestionDecision,
    TrustMetric,
    TrustMetricHistoryEntry,
)


def test_communication_profile_defaults_are_static() -> None:
    profile = CommunicationProfile(user_id=uuid4())
    assert profile.verbosity == "moderate"
    assert profile.technical_depth == "moderate"
    assert profile.terminology_preference is None
    assert profile.conversation_pacing is None
    assert profile.habit_timing_hint is None
    assert profile.source == "static_default"


def test_preference_evolution_entry_round_trips() -> None:
    entry = PreferenceEvolutionEntry(
        user_id=uuid4(),
        field="verbosity",
        previous_value="moderate",
        new_value="concise",
        confidence=0.8,
        source="test",
        reason="3 consecutive consistent observations",
    )
    assert entry.previous_value == "moderate"
    assert entry.new_value == "concise"


def test_habit_signal_is_structural_not_a_label() -> None:
    signal = HabitSignal(
        user_id=uuid4(),
        session_id=uuid4(),
        turn_count=5,
        session_duration_seconds=612.0,
        observed_at=datetime.now(UTC),
    )
    assert signal.turn_count == 5


def test_completed_session_evidence_defaults_to_empty_lists() -> None:
    evidence = CompletedSessionEvidence(
        session_id=uuid4(), user_id=uuid4(), turn_count=0, closed_at=datetime.now(UTC)
    )
    assert evidence.corrections == []
    assert evidence.preferences == []
    assert evidence.feedback == []
    assert evidence.decisions == []


def test_trust_metric_defaults_reserve_unpopulated_inputs() -> None:
    metric = TrustMetric(user_id=uuid4())
    assert metric.correction_frequency is None
    assert metric.clarification_acceptance_rate is None
    assert metric.proactive_suggestion_acceptance_rate is None


def test_trust_metric_history_entry_round_trips() -> None:
    entry = TrustMetricHistoryEntry(
        user_id=uuid4(), correction_frequency=0.5, window_session_count=4
    )
    assert entry.correction_frequency == 0.5


def test_proactive_boundary_policy_defaults() -> None:
    policy = ProactiveBoundaryPolicy(user_id=uuid4())
    assert policy.enabled is True
    assert policy.max_per_topic_per_window == {}
    assert policy.window_hours == 24


def test_proactive_suggestion_and_delivery_record_round_trip() -> None:
    suggestion = ProactiveSuggestion(topic="deploy", content="Your build finished.")
    assert suggestion.topic == "deploy"
    delivery = ProactiveDeliveryRecord(topic="deploy", delivered_at=datetime.now(UTC))
    assert delivery.topic == "deploy"


def test_proactive_suggestion_decision_always_carries_a_reason() -> None:
    decision = ProactiveSuggestionDecision(allowed=True, reason="within configured frequency limit")
    assert decision.reason

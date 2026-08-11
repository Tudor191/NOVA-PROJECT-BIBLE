from datetime import UTC, datetime
from uuid import uuid4

from nova_digital_twin_engine.domain import trust_metric
from nova_digital_twin_engine.domain.models import CompletedSessionEvidence


def _session(**overrides: object) -> CompletedSessionEvidence:
    defaults: dict[str, object] = dict(
        session_id=uuid4(),
        user_id=uuid4(),
        turn_count=4,
        closed_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return CompletedSessionEvidence(**defaults)  # type: ignore[arg-type]


def test_no_sessions_returns_none_not_zero() -> None:
    assert trust_metric.compute_correction_frequency([]) is None


def test_correction_frequency_is_the_average_corrections_per_session() -> None:
    sessions = [
        _session(corrections=["It's Tuesday, not Wednesday."]),
        _session(corrections=[]),
        _session(corrections=["No, the other one.", "Not that file."]),
    ]
    assert trust_metric.compute_correction_frequency(sessions) == 1.0


def test_correction_frequency_ignores_other_memory_categories() -> None:
    sessions = [
        _session(
            corrections=[],
            preferences=["Prefers concise responses."],
            feedback=["That was helpful."],
            decisions=["Proceed with option B."],
        )
    ]
    assert trust_metric.compute_correction_frequency(sessions) == 0.0


def test_compute_trust_metric_reserves_the_not_yet_computed_fields() -> None:
    user_id = uuid4()
    sessions = [_session(user_id=user_id, corrections=["fix that"])]
    metric = trust_metric.compute_trust_metric(user_id=user_id, sessions=sessions)
    assert metric.user_id == user_id
    assert metric.correction_frequency == 1.0
    assert metric.window_session_count == 1
    assert metric.clarification_acceptance_rate is None
    assert metric.proactive_suggestion_acceptance_rate is None

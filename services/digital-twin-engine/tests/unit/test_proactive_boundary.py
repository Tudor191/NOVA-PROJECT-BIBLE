from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_digital_twin_engine.domain import proactive_boundary
from nova_digital_twin_engine.domain.models import (
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    ProactiveSuggestion,
)

_NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def test_disabled_policy_denies_regardless_of_topic() -> None:
    policy = ProactiveBoundaryPolicy(
        user_id=uuid4(), enabled=False, max_per_topic_per_window={"deploy": 5}
    )
    decision = proactive_boundary.evaluate_proactive_suggestion(
        policy=policy,
        suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
        recent_deliveries=[],
        now=_NOW,
    )
    assert decision.allowed is False
    assert "disabled" in decision.reason


def test_unconfigured_topic_is_denied_not_allowed() -> None:
    """Sec10.1 -- no implicit default per topic; an unconfigured topic is a
    boundary the user has not yet set, not evidence that none is wanted."""
    policy = ProactiveBoundaryPolicy(user_id=uuid4(), max_per_topic_per_window={})
    decision = proactive_boundary.evaluate_proactive_suggestion(
        policy=policy,
        suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
        recent_deliveries=[],
        now=_NOW,
    )
    assert decision.allowed is False
    assert "no configured frequency limit" in decision.reason


def test_within_the_configured_limit_is_allowed() -> None:
    policy = ProactiveBoundaryPolicy(user_id=uuid4(), max_per_topic_per_window={"deploy": 2})
    decision = proactive_boundary.evaluate_proactive_suggestion(
        policy=policy,
        suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
        recent_deliveries=[
            ProactiveDeliveryRecord(
                user_id=uuid4(), topic="deploy", delivered_at=_NOW - timedelta(hours=1)
            )
        ],
        now=_NOW,
    )
    assert decision.allowed is True


def test_at_the_configured_limit_is_denied() -> None:
    policy = ProactiveBoundaryPolicy(user_id=uuid4(), max_per_topic_per_window={"deploy": 2})
    recent = [
        ProactiveDeliveryRecord(
            user_id=uuid4(), topic="deploy", delivered_at=_NOW - timedelta(hours=1)
        ),
        ProactiveDeliveryRecord(
            user_id=uuid4(), topic="deploy", delivered_at=_NOW - timedelta(hours=2)
        ),
    ]
    decision = proactive_boundary.evaluate_proactive_suggestion(
        policy=policy,
        suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
        recent_deliveries=recent,
        now=_NOW,
    )
    assert decision.allowed is False
    assert "2 of 2" in decision.reason


def test_deliveries_outside_the_window_do_not_count() -> None:
    policy = ProactiveBoundaryPolicy(
        user_id=uuid4(), max_per_topic_per_window={"deploy": 1}, window_hours=24
    )
    stale = ProactiveDeliveryRecord(
        user_id=uuid4(), topic="deploy", delivered_at=_NOW - timedelta(hours=48)
    )
    decision = proactive_boundary.evaluate_proactive_suggestion(
        policy=policy,
        suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
        recent_deliveries=[stale],
        now=_NOW,
    )
    assert decision.allowed is True


def test_deliveries_for_a_different_topic_do_not_count() -> None:
    policy = ProactiveBoundaryPolicy(user_id=uuid4(), max_per_topic_per_window={"deploy": 1})
    other_topic = ProactiveDeliveryRecord(
        user_id=uuid4(), topic="calendar", delivered_at=_NOW - timedelta(hours=1)
    )
    decision = proactive_boundary.evaluate_proactive_suggestion(
        policy=policy,
        suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
        recent_deliveries=[other_topic],
        now=_NOW,
    )
    assert decision.allowed is True

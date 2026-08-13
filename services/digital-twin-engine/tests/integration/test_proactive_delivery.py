"""`proactive_delivery.attempt_proactive_delivery` (Phase 2D-D docs/design/
phase-2d/06-personal-companion.md Sec10.2, Fork D) -- the warm-case
delivery orchestration: policy check, `user_id -> connected session_id`
lookup, and the existing `communication.intent.deliver.request` gate,
composed against a real `FakeDigitalTwinRepository` and a `FakeCommunicationPort`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.domain.models import (
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    ProactiveSuggestion,
)
from nova_digital_twin_engine.main import create_app
from nova_digital_twin_engine.proactive_delivery import attempt_proactive_delivery

from tests.fakes.ports import FakeCommunicationPort
from tests.fakes.repository import FakeDigitalTwinRepository

_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


async def test_denied_by_policy_never_reaches_the_communication_port(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={}
    )
    communication_port = FakeCommunicationPort()
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None
    assert communication_port.get_connected_session_calls == []
    assert repository.proactive_deliveries == []


async def test_no_stored_policy_defaults_to_a_deny(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Sec10.1's fail-closed discipline -- a brand-new user with no
    configured policy denies every topic, without this function
    special-casing "no policy" separately from "no limit for this topic"."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    communication_port = FakeCommunicationPort()
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None
    assert communication_port.get_connected_session_calls == []


async def test_allowed_but_no_connected_session_is_the_cold_case_no_op(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Sec10.3 -- allowed by policy, but the user has no currently-connected
    session: no delivery is attempted, no error is raised."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={"deploy": 5}
    )
    communication_port = FakeCommunicationPort(connected_session_id=None)
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None
    assert communication_port.get_connected_session_calls == [user_id]
    assert communication_port.deliver_intent_calls == []
    assert repository.proactive_deliveries == []


async def test_allowed_and_connected_delivers_and_records_the_delivery(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    session_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={"deploy": 5}
    )
    communication_port = FakeCommunicationPort(
        connected_session_id=session_id, deliver_result=True
    )
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is not None
    assert record.user_id == user_id
    assert record.topic == "deploy"
    assert record.delivered_at == _NOW
    assert communication_port.deliver_intent_calls == [(session_id, "Your build finished.")]
    assert repository.proactive_deliveries == [record]


async def test_a_personality_rejected_delivery_is_not_recorded(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """`deliver_intent` returning `False` (a personality rejection or
    channel-level failure, `domain.ports.CommunicationPort`'s own
    documented distinction) must not count toward the rate limit -- only a
    real delivery does."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={"deploy": 5}
    )
    communication_port = FakeCommunicationPort(
        connected_session_id=uuid4(), deliver_result=False
    )
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None
    assert repository.proactive_deliveries == []


async def test_a_lookup_timeout_degrades_to_no_delivery_without_raising(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={"deploy": 5}
    )
    communication_port = FakeCommunicationPort(raise_lookup_timeout=True)
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None


async def test_a_deliver_timeout_degrades_to_no_delivery_without_raising(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={"deploy": 5}
    )
    communication_port = FakeCommunicationPort(
        connected_session_id=uuid4(), raise_deliver_timeout=True
    )
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None


async def test_recent_deliveries_within_the_window_deny_a_repeat_delivery(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """Proves `attempt_proactive_delivery` actually threads real,
    previously-recorded deliveries into `evaluate_proactive_suggestion` --
    not just that the policy function itself works in isolation
    (`test_proactive_boundary.py` already covers that)."""
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    user_id = uuid4()
    repository = FakeDigitalTwinRepository()
    repository.proactive_policies[user_id] = ProactiveBoundaryPolicy(
        user_id=user_id, max_per_topic_per_window={"deploy": 1}, window_hours=24
    )
    repository.proactive_deliveries.append(
        ProactiveDeliveryRecord(
            user_id=user_id, topic="deploy", delivered_at=_NOW - timedelta(hours=1)
        )
    )
    communication_port = FakeCommunicationPort(connected_session_id=uuid4())
    app = create_app(Settings(), repository=repository, communication_port=communication_port)

    async with app.router.lifespan_context(app):
        record = await attempt_proactive_delivery(
            app,
            user_id=user_id,
            suggestion=ProactiveSuggestion(topic="deploy", content="Your build finished."),
            now=_NOW,
        )

    assert record is None
    assert communication_port.get_connected_session_calls == []

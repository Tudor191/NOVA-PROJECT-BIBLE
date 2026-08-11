"""`communication.session.completed` subscribed handler
(`events/handlers.py::make_session_completed_handler`) -- records raw
evidence + a structural habit signal, recomputes the correction-frequency
trust metric over the configured rolling window (docs/design/phase-2d/
06-personal-companion.md Sec9, Sec11.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nova_contracts import CommunicationSessionCompletedPayload, EventEnvelope
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.events.handlers import make_session_completed_handler
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


def _envelope(payload: CommunicationSessionCompletedPayload) -> EventEnvelope:
    return EventEnvelope(
        subject="communication.session.completed",
        source_engine="communication-engine",
        correlation_id=uuid4(),
        payload=payload.model_dump(mode="json"),
    )


async def test_records_completed_session_evidence_and_habit_signal(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        payload = CommunicationSessionCompletedPayload(
            session_id=uuid4(),
            user_id=user_id,
            turn_count=6,
            closed_at=datetime.now(UTC),
            corrections=["It's Tuesday, not Wednesday."],
        )
        await make_session_completed_handler(app)(_envelope(payload))

        assert len(repository.completed_sessions) == 1
        assert repository.completed_sessions[0].corrections == ["It's Tuesday, not Wednesday."]
        assert len(repository.habit_signals) == 1
        assert repository.habit_signals[0].turn_count == 6
        assert repository.habit_signals[0].user_id == user_id


async def test_recomputes_and_persists_the_trust_metric(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        handler = make_session_completed_handler(app)

        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(),
                    user_id=user_id,
                    turn_count=4,
                    closed_at=datetime.now(UTC),
                    corrections=["fix that"],
                )
            )
        )
        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(),
                    user_id=user_id,
                    turn_count=3,
                    closed_at=datetime.now(UTC),
                )
            )
        )

        metric = repository.trust_metrics[user_id]
        assert metric.correction_frequency == 0.5
        assert metric.window_session_count == 2
        assert metric.clarification_acceptance_rate is None
        assert metric.proactive_suggestion_acceptance_rate is None


async def test_a_changed_trust_metric_writes_a_history_entry(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        handler = make_session_completed_handler(app)

        # First session: metric goes from unset (None) to 0.0 -- a change.
        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(), user_id=user_id, turn_count=2, closed_at=datetime.now(UTC)
                )
            )
        )
        assert len(repository.trust_metric_history) == 1
        assert repository.trust_metric_history[0].correction_frequency == 0.0

        # Second session, still zero corrections: 0.0 -> 0.0, no change.
        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(), user_id=user_id, turn_count=3, closed_at=datetime.now(UTC)
                )
            )
        )
        assert len(repository.trust_metric_history) == 1


async def test_only_the_configured_window_of_sessions_is_considered(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeDigitalTwinRepository()
    settings = Settings(trust_metric_window_size=2)
    app = create_app(settings, repository=repository)

    async with app.router.lifespan_context(app):
        user_id = uuid4()
        handler = make_session_completed_handler(app)

        # Oldest session has 5 corrections but falls outside the 2-session window.
        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(),
                    user_id=user_id,
                    turn_count=1,
                    closed_at=datetime(2026, 1, 1, tzinfo=UTC),
                    corrections=["a", "b", "c", "d", "e"],
                )
            )
        )
        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(),
                    user_id=user_id,
                    turn_count=1,
                    closed_at=datetime(2026, 1, 2, tzinfo=UTC),
                )
            )
        )
        await handler(
            _envelope(
                CommunicationSessionCompletedPayload(
                    session_id=uuid4(),
                    user_id=user_id,
                    turn_count=1,
                    closed_at=datetime(2026, 1, 3, tzinfo=UTC),
                )
            )
        )

        metric = repository.trust_metrics[user_id]
        assert metric.window_session_count == 2
        assert metric.correction_frequency == 0.0

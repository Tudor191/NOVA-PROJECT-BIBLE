"""`events/handlers.py` -- `make_session_dispatch_handler` (docs/design/
phase-2d/03-perception-engine.md §13.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nova_contracts import EventEnvelope
from nova_perception_engine.domain.session_activity import SessionActivityTracker
from nova_perception_engine.events.handlers import make_session_dispatch_handler


def _envelope(subject: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        subject=subject,
        source_engine="communication-engine",
        correlation_id=uuid4(),
        causation_id=None,
        payload=payload,
        occurred_at=datetime.now(UTC),
    )


async def test_session_created_marks_user_active() -> None:
    tracker = SessionActivityTracker()
    handler = make_session_dispatch_handler(tracker)
    user_id, session_id = uuid4(), uuid4()

    await handler(
        _envelope(
            "communication.session.created",
            {"session_id": str(session_id), "user_id": str(user_id)},
        )
    )

    assert tracker.is_active(user_id=user_id) is True


async def test_session_completed_clears_activity() -> None:
    tracker = SessionActivityTracker()
    handler = make_session_dispatch_handler(tracker)
    user_id, session_id = uuid4(), uuid4()
    tracker.session_created(user_id=user_id, session_id=session_id)

    await handler(
        _envelope(
            "communication.session.completed",
            {"session_id": str(session_id), "user_id": str(user_id)},
        )
    )

    assert tracker.is_active(user_id=user_id) is False


async def test_missing_user_id_is_skipped_not_raised() -> None:
    tracker = SessionActivityTracker()
    handler = make_session_dispatch_handler(tracker)

    await handler(
        _envelope("communication.session.created", {"session_id": str(uuid4())})
    )  # no raise, no state change

    assert tracker._active_sessions_by_user == {}


async def test_missing_session_id_is_skipped_not_raised() -> None:
    tracker = SessionActivityTracker()
    handler = make_session_dispatch_handler(tracker)

    await handler(
        _envelope("communication.session.created", {"user_id": str(uuid4())})
    )  # no raise, no state change

    assert tracker._active_sessions_by_user == {}

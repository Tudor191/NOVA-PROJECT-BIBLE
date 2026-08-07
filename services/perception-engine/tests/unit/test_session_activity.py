"""`domain/session_activity.py` -- `SessionActivityTracker` (docs/design/
phase-2d/03-perception-engine.md §10)."""

from __future__ import annotations

from uuid import uuid4

from nova_perception_engine.domain.session_activity import SessionActivityTracker


def test_is_active_false_before_any_session() -> None:
    tracker = SessionActivityTracker()
    assert tracker.is_active(user_id=uuid4()) is False


def test_session_created_marks_user_active() -> None:
    tracker = SessionActivityTracker()
    user_id, session_id = uuid4(), uuid4()
    tracker.session_created(user_id=user_id, session_id=session_id)
    assert tracker.is_active(user_id=user_id) is True


def test_session_ended_clears_activity() -> None:
    tracker = SessionActivityTracker()
    user_id, session_id = uuid4(), uuid4()
    tracker.session_created(user_id=user_id, session_id=session_id)
    tracker.session_ended(user_id=user_id, session_id=session_id)
    assert tracker.is_active(user_id=user_id) is False


def test_one_session_ending_does_not_clear_a_still_active_second_session() -> None:
    tracker = SessionActivityTracker()
    user_id = uuid4()
    session_a, session_b = uuid4(), uuid4()
    tracker.session_created(user_id=user_id, session_id=session_a)
    tracker.session_created(user_id=user_id, session_id=session_b)

    tracker.session_ended(user_id=user_id, session_id=session_a)

    assert tracker.is_active(user_id=user_id) is True


def test_ending_an_unknown_session_is_a_no_op() -> None:
    tracker = SessionActivityTracker()
    tracker.session_ended(user_id=uuid4(), session_id=uuid4())  # no raise

"""`domain.correlation_buffer.WindowCorrelationBuffer` -- freshness and
expiry of both the wake and gaze channels, independently."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nova_contracts.events.perception import GazeDirection
from nova_perception_engine.domain.correlation_buffer import WindowCorrelationBuffer


def test_nothing_recorded_returns_the_honest_absent_defaults() -> None:
    buffer = WindowCorrelationBuffer()
    wake_matched, wake_confidence, gaze_direction = buffer.current(window_seconds=2.5)
    assert wake_matched is False
    assert wake_confidence == 0.0
    assert gaze_direction is GazeDirection.UNKNOWN


def test_a_fresh_wake_contribution_is_reported() -> None:
    buffer = WindowCorrelationBuffer()
    now = datetime.now(UTC)
    buffer.record_wake(matched=True, confidence=1.0, now=now)
    wake_matched, wake_confidence, _ = buffer.current(window_seconds=2.5, now=now)
    assert wake_matched is True
    assert wake_confidence == 1.0


def test_a_fresh_gaze_contribution_is_reported() -> None:
    buffer = WindowCorrelationBuffer()
    now = datetime.now(UTC)
    buffer.record_gaze(GazeDirection.TOWARD_DEVICE, now=now)
    _, _, gaze_direction = buffer.current(window_seconds=2.5, now=now)
    assert gaze_direction is GazeDirection.TOWARD_DEVICE


def test_a_contribution_exactly_at_the_window_boundary_still_counts() -> None:
    buffer = WindowCorrelationBuffer()
    recorded_at = datetime.now(UTC)
    buffer.record_wake(matched=True, confidence=1.0, now=recorded_at)
    later = recorded_at + timedelta(seconds=2.5)
    wake_matched, _, _ = buffer.current(window_seconds=2.5, now=later)
    assert wake_matched is True


def test_an_expired_wake_contribution_falls_back_to_absent() -> None:
    buffer = WindowCorrelationBuffer()
    recorded_at = datetime.now(UTC)
    buffer.record_wake(matched=True, confidence=1.0, now=recorded_at)
    later = recorded_at + timedelta(seconds=2.51)
    wake_matched, wake_confidence, _ = buffer.current(window_seconds=2.5, now=later)
    assert wake_matched is False
    assert wake_confidence == 0.0


def test_an_expired_gaze_contribution_falls_back_to_unknown() -> None:
    buffer = WindowCorrelationBuffer()
    recorded_at = datetime.now(UTC)
    buffer.record_gaze(GazeDirection.TOWARD_DEVICE, now=recorded_at)
    later = recorded_at + timedelta(seconds=2.51)
    _, _, gaze_direction = buffer.current(window_seconds=2.5, now=later)
    assert gaze_direction is GazeDirection.UNKNOWN


def test_wake_and_gaze_channels_expire_independently() -> None:
    buffer = WindowCorrelationBuffer()
    t0 = datetime.now(UTC)
    buffer.record_wake(matched=True, confidence=1.0, now=t0)
    t1 = t0 + timedelta(seconds=2.0)
    buffer.record_gaze(GazeDirection.TOWARD_DEVICE, now=t1)
    # At t1 + 1s, wake (recorded at t0) is 3s old -- expired; gaze
    # (recorded at t1) is 1s old -- still fresh.
    later = t1 + timedelta(seconds=1.0)
    wake_matched, _, gaze_direction = buffer.current(window_seconds=2.5, now=later)
    assert wake_matched is False
    assert gaze_direction is GazeDirection.TOWARD_DEVICE


def test_recording_a_new_wake_contribution_overwrites_the_previous_one() -> None:
    buffer = WindowCorrelationBuffer()
    now = datetime.now(UTC)
    buffer.record_wake(matched=True, confidence=1.0, now=now)
    buffer.record_wake(matched=False, confidence=0.0, now=now)
    wake_matched, _, _ = buffer.current(window_seconds=2.5, now=now)
    assert wake_matched is False

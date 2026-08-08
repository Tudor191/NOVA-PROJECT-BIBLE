"""In-process, ephemeral cross-sensor correlation buffer -- Priority 1 of
docs/design/phase-2d/05-conversation-intelligence-closure.md Sec3
(user-approved Fork #3, Option 1: a real ingestion endpoint accepting one
sensor's window per call, not a synchronized multi-sensor capture).

Because each ingestion call carries only one sensor's contribution, a
single observation window on its own could only ever report a wake-word
*or* a gaze signal, never both -- capping addressee-fusion's reachable
score well below what `config.py`'s own `correlation_window_seconds`
(Sec17's "continuous-reassessment cadence") was already named for. This
buffer remembers the most recent wake and gaze contributions, each with its
own observation time, so a call arriving for one sensor can still combine
with a still-fresh contribution from the other sensor -- the direct
implementation of that existing setting, not a new architectural concept.

Mirrors `SessionActivityTracker`'s own established pattern exactly: safe to
lose on restart, a single instance for the whole engine process, no
cross-tenant/cross-session keying -- consistent with ADR-025's single-
instance-per-deployment assumption, the same reasoning already applied
there.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nova_contracts.events.perception import GazeDirection

__all__ = ["WindowCorrelationBuffer"]


class WindowCorrelationBuffer:
    def __init__(self) -> None:
        self._wake: tuple[bool, float, datetime] | None = None
        self._gaze: tuple[GazeDirection, datetime] | None = None

    def record_wake(self, *, matched: bool, confidence: float, now: datetime | None = None) -> None:
        self._wake = (matched, confidence, now or datetime.now(UTC))

    def record_gaze(self, direction: GazeDirection, *, now: datetime | None = None) -> None:
        self._gaze = (direction, now or datetime.now(UTC))

    def current(
        self, *, window_seconds: float, now: datetime | None = None
    ) -> tuple[bool, float, GazeDirection]:
        """The freshest wake/gaze contributions still within
        `window_seconds` of `now` -- an expired or never-recorded
        contribution reports its honest "absent" default rather than a
        stale value."""
        moment = now or datetime.now(UTC)

        wake_matched, wake_confidence = False, 0.0
        if self._wake is not None:
            matched, confidence, observed_at = self._wake
            if (moment - observed_at).total_seconds() <= window_seconds:
                wake_matched, wake_confidence = matched, confidence

        gaze_direction = GazeDirection.UNKNOWN
        if self._gaze is not None:
            direction, observed_at = self._gaze
            if (moment - observed_at).total_seconds() <= window_seconds:
                gaze_direction = direction

        return wake_matched, wake_confidence, gaze_direction

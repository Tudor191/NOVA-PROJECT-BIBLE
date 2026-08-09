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

Priority 2 (docs/design/phase-2d/05-conversation-intelligence-closure.md
Sec4) adds a second, parallel channel alongside the wake/gaze one above:
per-modality identity-match signals (`ModalitySignal`, `domain/
identity_fusion.py`), keyed by modality rather than by sensor source, for
the same "one ingestion call, one sensor's contribution" reason the
wake/gaze channel exists -- a voice match from one call and a face match
from another, each still fresh, must combine through `fuse_window` exactly
as a real synchronized multi-sensor capture would have. Deliberately reuses
`fuse_window` rather than duplicating its agreement/disagreement logic here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nova_contracts.events.perception import GazeDirection

from nova_perception_engine.domain.identity_fusion import (
    FusedWindowResult,
    ModalitySignal,
    fuse_window,
)

__all__ = ["WindowCorrelationBuffer"]


class WindowCorrelationBuffer:
    def __init__(self) -> None:
        self._wake: tuple[bool, float, datetime] | None = None
        self._gaze: tuple[GazeDirection, datetime] | None = None
        self._identity_signals: dict[str, tuple[ModalitySignal, datetime]] = {}

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

    def record_identity_signal(
        self, signal: ModalitySignal, *, now: datetime | None = None
    ) -> None:
        self._identity_signals[signal.modality] = (signal, now or datetime.now(UTC))

    def current_identity(
        self, *, window_seconds: float, now: datetime | None = None
    ) -> FusedWindowResult:
        """The freshest per-modality identity signals still within
        `window_seconds` of `now`, fused via `identity_fusion.fuse_window` --
        an expired or never-recorded modality simply does not contribute,
        the same honest-absence convention `current()` above already
        applies to wake/gaze."""
        moment = now or datetime.now(UTC)
        fresh_signals = [
            signal
            for signal, observed_at in self._identity_signals.values()
            if (moment - observed_at).total_seconds() <= window_seconds
        ]
        return fuse_window(fresh_signals)

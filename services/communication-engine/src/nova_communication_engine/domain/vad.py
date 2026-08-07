"""Transport VAD -- design doc Sec1 component 2, Sec3.4, Sec4. A dumb,
local, low-latency signal-processing mechanism with exactly one job: know
when the user started and stopped producing audio. Explicitly **not**
Phase 2D-B's future presence/attention signals (Sec3.4 draws this boundary
precisely) -- this module never decides who is speaking or whether they are
addressing NOVA, only whether audio energy is present.

Deliberately takes an already-computed `energy_above_threshold` boolean per
tick rather than raw audio samples -- the actual acoustic energy detection
is a `VoiceChannelAdapter`/codec-layer concern (design doc Sec2's "wire-
format translation" responsibility), not this module's; `domain/` stays
framework- and hardware-free per every prior engine's own boundary.

One threshold serves both roles design doc Sec4 describes: a silence gap
shorter than `end_of_utterance_silence_ms` is bridged (Master Blueprint
Sec13.5 -- conversation continuity through transient loss); a gap at or
beyond it concludes the utterance actually ended.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ["TransportVad", "TransportVadConfig", "UtteranceEvent", "detect_barge_in"]


@dataclass(frozen=True)
class TransportVadConfig:
    end_of_utterance_silence_ms: float = 700.0
    """Design doc Sec4 -- also the transient-gap tolerance: below this, a
    silence gap does not end the utterance."""


class UtteranceEvent(StrEnum):
    STARTED = "started"
    CONTINUING = "continuing"
    ENDED = "ended"
    NO_CHANGE = "no_change"


class TransportVad:
    """One instance per in-progress voice turn. `feed()` is called once per
    audio tick (design doc Sec4's audio buffer driving this)."""

    def __init__(self, config: TransportVadConfig | None = None) -> None:
        self._config = config or TransportVadConfig()
        self._active = False
        self._last_energy_at_ms: float | None = None

    @property
    def active(self) -> bool:
        return self._active

    def feed(self, *, energy_above_threshold: bool, now_ms: float) -> UtteranceEvent:
        if energy_above_threshold:
            self._last_energy_at_ms = now_ms
            if not self._active:
                self._active = True
                return UtteranceEvent.STARTED
            return UtteranceEvent.CONTINUING

        if not self._active:
            return UtteranceEvent.NO_CHANGE

        assert self._last_energy_at_ms is not None  # _active implies this was already set
        gap_ms = now_ms - self._last_energy_at_ms
        if gap_ms >= self._config.end_of_utterance_silence_ms:
            self._active = False
            return UtteranceEvent.ENDED
        return UtteranceEvent.CONTINUING  # transient gap, bridged (Master Blueprint Sec13.5)

    def reset(self) -> None:
        self._active = False
        self._last_energy_at_ms = None


def detect_barge_in(*, energy_above_threshold: bool) -> bool:
    """Design doc Sec4 -- barge-in detection while `Speaking` is
    unconditional and immediate (Master Blueprint Sec13.4): any energy above
    threshold is a barge-in, no debounce, no policy judgment. Whether the
    interruption was *appropriate* is 2D-C's policy layer, never this
    module's (Doc 22 Principles 2-4, cited in design doc Sec16)."""
    return energy_above_threshold

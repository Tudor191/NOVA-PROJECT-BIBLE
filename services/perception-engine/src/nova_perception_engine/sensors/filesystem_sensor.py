"""The `"filesystem"` source's registry entry -- Phase 4F.3, **D-4F3-1**.

**This class performs no detection.** It holds no filesystem handle, opens no
watcher and reads no path. Real OS observation is `nova-companion`'s, in Rust
(TDD 4F.3 §5); this is the Python half of the ratified split, and it exists
because `handle_workspace_event` resolves `sensors_by_source[source]` and then
gates on `sensor.state() != "running"`. Without an entry under `"filesystem"`
every workspace observation 404s, which is exactly what 4F.2 shipped and
disclosed.

**Why that gate is the point rather than a formality.** It is what makes AC-7
clause 2's revocation real at the pipeline level: pausing this sensor makes the
engine drop in-flight observations from the companion, whatever the companion
is still doing. A source with no `Sensor` behind it could not be paused at all.

`VoiceSensor` and `CameraSensor` are the precedent -- both are perception-engine
classes representing a capability executed elsewhere (there, the
`ai-model-orchestration-engine` RPC boundary). This is the same shape with a
different elsewhere.

**Not implemented here, deliberately:** `detect_presence`, `detect_wake_phrase`,
`estimate_attention`, `match_voiceprint`, `match_faceprint`. Those belong to the
biometric window pipeline, which a structured workspace observation never
enters. The `Sensor` Protocol does not require them -- it requires the lifecycle
and description methods below, all of which are real.
"""

from __future__ import annotations

from nova_observability import get_logger
from nova_perception_engine.domain.sensor import (
    CalibrationResult,
    PermissionStatus,
    SensorConfig,
    SensorErrorReport,
    SensorHealth,
    SensorState,
    next_state,
)

__all__ = ["FilesystemSensor"]

logger = get_logger("perception-engine.sensors.filesystem")

SENSOR_ID = "companion-filesystem"
SOURCE = "filesystem"


class FilesystemSensor:
    """The lifecycle and permission representation of the companion's watcher.

    Implements the same `Sensor` Protocol and the same state machine as every
    other sensor, in full -- 2D-B's rule that the interface contract is
    complete from day one regardless of sensing breadth.
    """

    sensor_id = SENSOR_ID

    def __init__(self) -> None:
        self._state: SensorState = "uninitialized"
        self._errors: list[SensorErrorReport] = []

    # -- lifecycle ---------------------------------------------------------
    #
    # Every transition goes through `domain/sensor.py::next_state`, which
    # rejects undefined pairs by returning `None`. Re-implementing the ladder
    # here would give it two definitions, and the one nobody reads would be the
    # one that drifts.

    def _transition(self, action: str) -> None:
        resolved = next_state(self._state, action)
        if resolved is None:
            # Not an error: the same "no defined transition is a no-op"
            # convention `api/consent.py`'s revocation handler already relies on
            # when it stops an already-stopped sensor.
            logger.info(
                "filesystem_sensor_transition_ignored",
                extra={"sensor_id": self.sensor_id, "state": self._state, "action": action},
            )
            return
        self._state = resolved

    async def initialize(self) -> None:
        self._transition("initialize")

    async def start(self) -> None:
        self._transition("start")

    async def pause(self) -> None:
        self._transition("pause")

    async def resume(self) -> None:
        self._transition("resume")

    async def stop(self) -> None:
        self._transition("stop")

    def state(self) -> SensorState:
        return self._state

    # -- description -------------------------------------------------------

    async def health_check(self) -> SensorHealth:
        """Availability is this engine's view of the source, not a probe of the
        companion.

        There is no channel to ask the companion how it is: it is a client that
        speaks to this engine, never the reverse, and adding a callback would
        give it the listening port TDD 4F §7 forbids. So health reports the
        registry's own state and says so, rather than implying a liveness check
        that never happened.
        """
        running = self._state == "running"
        return SensorHealth(
            available=running,
            error_rate=0.0,
            detail=(
                "registry entry for the nova-companion filesystem source; "
                "reports this engine's lifecycle state, not a probe of the companion"
            ),
        )

    def configuration(self) -> SensorConfig:
        return SensorConfig(sensor_id=self.sensor_id, sensor_type="filesystem", parameters={})

    async def calibrate(self) -> CalibrationResult:
        """Nothing to calibrate. A filesystem event is discrete and exact --
        there is no threshold to tune, unlike an audio energy gate or a
        similarity score. Reported honestly rather than returning a success
        that describes no work."""
        return CalibrationResult(
            success=True, detail="filesystem observation requires no calibration"
        )

    def permission_status(self) -> PermissionStatus:
        """**Not a consent claim.**

        `granted` reflects that the *engine* imposes no OS-level permission on
        this source: whether the companion can read the directory it was
        configured with is enforced by the operating system, in the companion's
        own process, and this engine cannot observe it.

        **D-4F3-3 is explicit that 4F.3 adds no consent mechanism**, and this
        method must not be read as one. Doc 22 Principle 8's per-source consent
        requirement for the filesystem source remains an open policy question,
        carried as ledger row **L-14**. What bounds the risk meanwhile is that
        the companion watches only an explicitly configured directory.
        """
        return PermissionStatus(granted=True, source=SOURCE)

    def capabilities(self) -> frozenset[str]:
        return frozenset({"workspace_observation"})

    def report_error(self, error: SensorErrorReport) -> None:
        self._errors.append(error)
        # `detail`, not `message`: `message` is reserved on `LogRecord` and
        # `logging` raises `KeyError` rather than dropping it, so this would
        # have blown up the first time a sensor error was reported.
        logger.warning(
            "filesystem_sensor_error",
            extra={"sensor_id": self.sensor_id, "detail": error.message},
        )

    @property
    def errors(self) -> list[SensorErrorReport]:
        return list(self._errors)

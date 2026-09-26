"""Report a sensor's lifecycle transition on `perception.sensor.health_changed`
-- Phase 4F.7, TDD 4F §24.4 **RS-3a** and TDD 4F.7 §8.1, with the published
vocabulary ratified as **A-4F7-2** (TDD 4F.7 §28.2).

Each existing lifecycle call site -- startup, consent revocation, an
observation-window failure, shutdown -- goes through one of the two functions
below instead of calling the sensor directly. Each reads `sensor.state()`
before and after the call, and **only when the state actually changed**
enqueues one `perception.sensor.health_changed` whose `status` is the state
**after** the call:

- **The vocabulary is `SensorState`'s**, by construction: `status` is
  `sensor.state()`, never `health_check()`'s `"healthy"` / `"unhealthy"`
  string, and never a value invented here. The contract is unchanged
  (`status: str`).
- **No report for a no-op.** An undefined `(state, action)` pair leaves the
  sensor where it was (`domain/sensor.py::next_state`); reporting it would
  fabricate a change.
- **The `Sensor` Protocol is unchanged** (TDD 4F §7.2). The report is made at
  the call site, not inside a sensor class, and no transition is added --
  `pause` / `resume` have no production caller and gain none, and the
  filesystem sensor still has no path to `failed` (RS-3b, OPEN).
- **Through the existing transactional outbox** (TDD 4F §1.1(a), D-4F-1): no
  direct publish and no push dispatch. The existing worker dispatches it on
  its cron, so the envelope's `occurred_at` is dispatch time.

**An enqueue failure is logged, not raised.** A failure of the sensor call
itself propagates exactly as it did before this module existed. But the report
is an observation *about* a transition that has already happened, so failing
to queue it must not undo, or abort, the work that performed it: startup must
not refuse to serve because a status report could not be queued, a consent
revocation has already stopped its sensor, and an observation failure has
already been handled. This adds no retry, replay or recovery; a report that
could not be queued is lost, and the log says so.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from nova_observability import get_logger

from nova_perception_engine.domain.ports import PerceptionRepository
from nova_perception_engine.domain.sensor import Sensor, SensorErrorReport, SensorState
from nova_perception_engine.events import publishers

__all__ = ["LifecycleAction", "report_sensor_error", "transition"]

logger = get_logger("perception-engine.sensor_lifecycle")

LifecycleAction = Literal["initialize", "start", "stop"]
"""The three lifecycle calls production code makes today. `pause` and `resume`
exist on the Protocol but have no production caller, and 4F.7 gives them
none."""


async def transition(
    sensor: Sensor,
    action: LifecycleAction,
    *,
    repository: PerceptionRepository,
    correlation_id: UUID,
) -> None:
    """Perform `action` on `sensor`, and report the new state if it changed."""
    before = sensor.state()
    await getattr(sensor, action)()
    await _report_if_changed(sensor, before, repository=repository, correlation_id=correlation_id)


async def report_sensor_error(
    sensor: Sensor,
    error: SensorErrorReport,
    *,
    repository: PerceptionRepository,
    correlation_id: UUID,
) -> None:
    """`sensor.report_error(error)`, and report the new state if it changed.

    The camera and voice sensors move to `failed`; the filesystem sensor
    records the error and stays where it is, so nothing is reported for it --
    it has no `failed` path (RS-3b), and 4F.7 adds none."""
    before = sensor.state()
    sensor.report_error(error)
    await _report_if_changed(sensor, before, repository=repository, correlation_id=correlation_id)


async def _report_if_changed(
    sensor: Sensor,
    before: SensorState,
    *,
    repository: PerceptionRepository,
    correlation_id: UUID,
) -> None:
    after = sensor.state()
    if after == before:
        return
    event = publishers.sensor_health_changed(
        sensor_id=sensor.sensor_id,
        sensor_type=sensor.configuration().sensor_type,
        status=after,
        correlation_id=correlation_id,
    )
    try:
        await repository.enqueue_outbox(event)
    except Exception:
        logger.exception(
            "sensor_lifecycle_report_not_enqueued",
            extra={
                "sensor_id": sensor.sensor_id,
                "state": after,
                "correlation_id": str(correlation_id),
            },
        )

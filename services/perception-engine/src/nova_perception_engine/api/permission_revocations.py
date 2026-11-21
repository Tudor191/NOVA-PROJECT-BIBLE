"""`POST /v1/perception/permission-revocations` -- Phase 4F.8, A-4F8-1 (a) with
(a1) and (a2), ratified 2026-10-11 (TDD 4F.8 §29.1). RS-3b's owner.

**The one internal route through which `nova-companion` reports that it lost
its OS permission on the directory it watches.** The companion is the only
process that holds that permission, so detection is the companion's. Everything
after the report is this engine's, because this engine owns the sensor
lifecycle (TDD 4F §10):

- the filesystem sensor moves `running -> failed` through the existing error
  path, `sensor_lifecycle.report_sensor_error`, exactly as camera and voice do;
- that path publishes `failed` on `perception.sensor.health_changed` through the
  transactional outbox (4F.7), so the Cognitive State panel can show it;
- the existing `running` gate in `workspace_orchestration.py` then drops every
  later workspace observation.

**What this route is not:**

- **Not fronted by `api-gateway`.** `/v1/perception` is not one of its
  prefixes, so no browser can reach it. The companion speaks to this engine on
  the internal network, as it already does for workspace observations, whose
  contract this route leaves unchanged.
- **Not a consent mechanism.** It records an OS permission loss, not app
  consent (RS-3a's Option C analysis); `api/consent.py` is untouched.
- **Not an inference.** Nothing here, or anywhere, moves the sensor to `failed`
  because observations stopped arriving (N-8). This route is the only caller
  that reports `kind="permission_revoked"`.
- **Not a recovery path** (a2). A repeat report finds the sensor already
  `failed` and changes nothing. A re-granted permission takes effect only after
  the companion and this engine restart.

**No subject, no `PUBLIC_TOPICS` entry and no gateway prefix is added.**
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from nova_observability import get_logger
from pydantic import BaseModel, ConfigDict

from nova_perception_engine import sensor_lifecycle
from nova_perception_engine.domain.sensor import SensorErrorReport, SensorState

router = APIRouter(tags=["observations"])

logger = get_logger("perception-engine.permission_revocations")

REPORTING_SOURCES = frozenset({"filesystem"})
"""The sources a capturing process reports a permission loss for. Only
`nova-companion` captures outside this engine, and it feeds only the filesystem
source. Any other source is refused, so this route can never fail a sensor it
was not ratified for."""


class PermissionRevocationRequest(BaseModel):
    """What the companion sends. **No path and no identity**: the engine
    already knows which source it registered, and a path is user data."""

    model_config = ConfigDict(extra="forbid")

    detected_at: datetime
    """When the companion found out. A detection time, not the moment of the
    `chmod`, which the OS does not report."""


class PermissionRevocationOutcome(BaseModel):
    sensor_id: str
    state: SensorState
    transitioned: bool
    """Whether this report moved the sensor. `False` for a repeat."""


@router.post(
    "/v1/perception/permission-revocations",
    response_model=PermissionRevocationOutcome,
    status_code=202,
)
async def report_permission_revocation(
    request: Request,
    report: PermissionRevocationRequest,
    source: str,
    correlation_id: UUID | None = None,
) -> PermissionRevocationOutcome:
    state = request.app.state
    sensor = state.sensors_by_source.get(source) if source in REPORTING_SOURCES else None
    if sensor is None:
        raise HTTPException(
            status_code=404, detail=f"No permission reporter for source {source!r}."
        )

    before = sensor.state()
    await sensor_lifecycle.report_sensor_error(
        sensor,
        SensorErrorReport(
            sensor_id=sensor.sensor_id,
            message="the capturing process lost its OS permission on the watched directory",
            occurred_at=report.detected_at.isoformat(),
            kind="permission_revoked",
        ),
        repository=state.repository,
        correlation_id=correlation_id or uuid4(),
    )
    after = sensor.state()
    logger.warning(
        "sensor_permission_revoked",
        extra={"sensor_id": sensor.sensor_id, "state": after, "transitioned": after != before},
    )
    return PermissionRevocationOutcome(
        sensor_id=sensor.sensor_id, state=after, transitioned=after != before
    )

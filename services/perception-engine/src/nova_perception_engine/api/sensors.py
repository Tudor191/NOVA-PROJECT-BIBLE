"""`/v1/perception/sensors`, `/v1/perception/diagnostics`
(docs/design/phase-2d/03-perception-engine.md §5, §12, §14) -- Sensor Health
Status, Calibration, and a diagnostics dump. "Register Sensor"/"Remove
Sensor" are deliberately not exposed here (§14: startup-time configuration
in `main.py`, not a runtime API surface this phase).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nova_perception_engine.domain.sensor import CalibrationResult, SensorState

router = APIRouter(tags=["sensors"])


class SensorStatusResponse(BaseModel):
    sensor_id: str
    sensor_type: str
    state: SensorState
    available: bool
    capabilities: list[str]


@router.get("/v1/perception/sensors", response_model=list[SensorStatusResponse])
async def list_sensors(request: Request) -> list[SensorStatusResponse]:
    responses = []
    for sensor_id, sensor in request.app.state.sensors_by_id.items():
        health = await sensor.health_check()
        responses.append(
            SensorStatusResponse(
                sensor_id=sensor_id,
                sensor_type=sensor.configuration().sensor_type,
                state=sensor.state(),
                available=health.available,
                capabilities=sorted(sensor.capabilities()),
            )
        )
    return responses


@router.post("/v1/perception/sensors/{sensor_id}/calibrate", response_model=CalibrationResult)
async def calibrate_sensor(sensor_id: str, request: Request) -> CalibrationResult:
    sensor = request.app.state.sensors_by_id.get(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")
    return await sensor.calibrate()


class DiagnosticsResponse(BaseModel):
    sensors: list[SensorStatusResponse]
    correlation_window_seconds: float


@router.get("/v1/perception/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(request: Request) -> DiagnosticsResponse:
    """A dump of what this engine can actually observe about itself right
    now -- current sensor state/health/capabilities and the configured
    correlation-window cadence. No per-window fusion history or error-count
    time series is tracked yet (§15's `sensor_registration.error_count`
    column exists but nothing increments it this phase), so this endpoint
    reports only what is genuinely available rather than fabricating a
    richer diagnostics surface than the implementation actually has (Doc 23
    §6)."""
    sensor_statuses = await list_sensors(request)
    return DiagnosticsResponse(
        sensors=sensor_statuses,
        correlation_window_seconds=request.app.state.settings.correlation_window_seconds,
    )

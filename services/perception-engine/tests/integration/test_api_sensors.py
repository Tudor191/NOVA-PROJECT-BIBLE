"""End-to-end tests through `api/sensors.py` -- Sensor Health Status,
Calibration, and the diagnostics dump (docs/design/phase-2d/
03-perception-engine.md §5, §12, §14).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    app = create_app(
        Settings(), repository=repository, ai_model_port=FakeAIModelOrchestrationPort()
    )
    with TestClient(app) as client:
        yield client


def test_list_sensors_reports_every_registered_sensor_running(harness) -> None:  # type: ignore[no-untyped-def]
    """*(Named `..._both_shipped_sensors_...` and pinned to two ids until Phase
    4F.3 registered the `filesystem` source. The set is asserted exactly, not
    loosened to a subset: a sensor appearing here unannounced is exactly what
    this should catch.)*"""
    response = harness.get("/v1/perception/sensors")
    assert response.status_code == 200
    body = response.json()
    ids = {s["sensor_id"] for s in body}
    assert ids == {"voice-sensor-1", "camera-sensor-1", "companion-filesystem"}
    assert all(s["state"] == "running" and s["available"] for s in body)


def test_calibrate_known_sensor_succeeds(harness) -> None:  # type: ignore[no-untyped-def]
    response = harness.post("/v1/perception/sensors/voice-sensor-1/calibrate")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_calibrate_unknown_sensor_is_404(harness) -> None:  # type: ignore[no-untyped-def]
    response = harness.post("/v1/perception/sensors/does-not-exist/calibrate")
    assert response.status_code == 404


def test_diagnostics_reports_sensors_and_correlation_window(harness) -> None:  # type: ignore[no-untyped-def]
    response = harness.get("/v1/perception/diagnostics")
    assert response.status_code == 200
    body = response.json()
    # Three since 4F.3 registered the `filesystem` source; two before it.
    assert len(body["sensors"]) == 3
    assert body["correlation_window_seconds"] == 2.5

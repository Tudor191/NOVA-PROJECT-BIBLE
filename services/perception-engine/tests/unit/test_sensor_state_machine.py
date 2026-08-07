"""`domain/sensor.py`'s lifecycle state machine (docs/design/phase-2d/
03-perception-engine.md Sec5)."""

from __future__ import annotations

from nova_perception_engine.domain.sensor import SensorState, next_state


def _advance(state: SensorState, action: str) -> SensorState:
    result = next_state(state, action)
    assert result is not None
    return result


def test_full_lifecycle_happy_path() -> None:
    state: SensorState = "uninitialized"
    state = _advance(state, "initialize")
    assert state == "initialized"
    state = _advance(state, "start")
    assert state == "running"
    state = _advance(state, "pause")
    assert state == "paused"
    state = _advance(state, "resume")
    assert state == "running"
    state = _advance(state, "stop")
    assert state == "stopped"


def test_paused_can_stop_directly() -> None:
    assert next_state("paused", "stop") == "stopped"


def test_failure_and_restart() -> None:
    assert next_state("running", "fail") == "failed"
    assert next_state("failed", "initialize") == "initialized"


def test_undefined_transition_returns_none() -> None:
    assert next_state("uninitialized", "start") is None
    assert next_state("stopped", "start") is None
    assert next_state("running", "initialize") is None

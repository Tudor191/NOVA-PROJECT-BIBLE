"""`FilesystemSensor` -- Phase 4F.3's registry entry (D-4F3-1).

The properties worth asserting are mostly about what this class *is not*: it
performs no detection, it makes no consent claim, and it re-implements no
lifecycle logic.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest
from nova_perception_engine.domain.sensor import Sensor, SensorErrorReport
from nova_perception_engine.sensors.filesystem_sensor import SOURCE, FilesystemSensor


def test_it_satisfies_the_sensor_protocol() -> None:
    """The 2D-B rule: every sensor implements the same Protocol in full, from
    day one, regardless of sensing breadth."""
    assert isinstance(FilesystemSensor(), Sensor)


async def test_the_lifecycle_follows_the_shared_state_machine() -> None:
    sensor = FilesystemSensor()
    assert sensor.state() == "uninitialized"

    await sensor.initialize()
    assert sensor.state() == "initialized"
    await sensor.start()
    assert sensor.state() == "running"
    await sensor.pause()
    assert sensor.state() == "paused"
    await sensor.resume()
    assert sensor.state() == "running"
    await sensor.stop()
    assert sensor.state() == "stopped"


async def test_an_undefined_transition_is_a_no_op_not_an_error() -> None:
    """`next_state` returns `None` for an undefined pair, and the established
    convention treats that as a no-op -- `api/consent.py`'s revocation handler
    already relies on it when stopping an already-stopped sensor."""
    sensor = FilesystemSensor()
    await sensor.start()  # illegal from `uninitialized`
    assert sensor.state() == "uninitialized"


async def test_pausing_is_what_makes_revocation_real_at_the_pipeline_level() -> None:
    """AC-7 clause 2. `handle_workspace_event` drops any observation whose
    sensor is not `running`, so a paused sensor stops the companion's events at
    the engine whatever the companion is still doing."""
    sensor = FilesystemSensor()
    await sensor.initialize()
    await sensor.start()
    await sensor.pause()
    assert sensor.state() != "running"


def test_it_declares_the_widened_sensor_type() -> None:
    config = FilesystemSensor().configuration()
    assert config.sensor_type == "filesystem"
    assert config.sensor_id == "companion-filesystem"


def test_the_permission_source_is_the_widened_literal() -> None:
    assert FilesystemSensor().permission_status().source == SOURCE == "filesystem"


async def test_health_reports_engine_state_and_says_so() -> None:
    """There is no channel to probe the companion -- it is a client, never a
    server -- so health must not imply a liveness check that never happened."""
    sensor = FilesystemSensor()
    unstarted = await sensor.health_check()
    assert unstarted.available is False

    await sensor.initialize()
    await sensor.start()
    started = await sensor.health_check()
    assert started.available is True
    assert "not a probe of the companion" in (started.detail or "")


def test_it_performs_no_detection_and_holds_no_filesystem_handle() -> None:
    """**D-4F3-1's central property, asserted structurally.**

    Real OS observation belongs to the Rust companion. If this class ever grows
    a watcher, a path read, or a biometric method, the split has been eroded and
    this fails.
    """
    # Docstrings stripped via the AST, the approach `cognitive-state-engine`'s
    # boundary tests established: this class's own prose explains at length what
    # the *companion* watches, and a substring check that could not tell a
    # citation from a call would force the code to stop explaining itself.
    tree = ast.parse(textwrap.dedent(inspect.getsource(FilesystemSensor)))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                node.body = node.body[1:] or [ast.Pass()]
    body = ast.unparse(tree)

    for forbidden in ("open(", "os.walk", "listdir", "watch", "inotify", "stat("):
        assert forbidden not in body, f"FilesystemSensor performs filesystem work: {forbidden!r}"

    biometrics = ("detect_presence", "detect_wake_phrase", "match_voiceprint", "match_faceprint")
    for biometric in biometrics:
        assert not hasattr(FilesystemSensor, biometric), (
            f"{biometric} belongs to the biometric window pipeline, which a workspace "
            "observation never enters"
        )


def test_permission_status_is_documented_as_not_a_consent_claim() -> None:
    """**D-4F3-3.** 4F.3 adds no consent mechanism, and `granted=True` must not
    be readable as one. The docstring is the control here, so it is asserted."""
    doc = FilesystemSensor.permission_status.__doc__ or ""
    assert "Not a consent claim" in doc
    assert "L-14" in doc


def test_reported_errors_are_retained_for_the_diagnostics_surface() -> None:
    sensor = FilesystemSensor()
    sensor.report_error(
        SensorErrorReport(
            sensor_id=sensor.sensor_id,
            message="watcher died",
            occurred_at="2026-09-16T00:00:00Z",
        )
    )
    assert [error.message for error in sensor.errors] == ["watcher died"]


async def test_calibration_reports_honestly_that_there_is_nothing_to_calibrate() -> None:
    result = await FilesystemSensor().calibrate()
    assert result.success is True
    assert "no calibration" in (result.detail or "")


@pytest.mark.parametrize("capability", ["workspace_observation"])
def test_capabilities_name_only_what_it_does(capability: str) -> None:
    assert FilesystemSensor().capabilities() == frozenset({capability})

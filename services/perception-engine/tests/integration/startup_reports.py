"""The six lifecycle reports every `create_app` startup now enqueues -- Phase 4F.7
(TDD 4F §24.4 RS-3a; TDD 4F.7 §8.1, A-4F7-2).

Since 4F.7, startup's `initialize()` / `start()` calls each report the state
they reached on `perception.sensor.health_changed`, through the outbox. Tests
written before 4F.7 count outbox rows from an empty outbox, so their harnesses
call `take_startup_reports` once the app has started: it **asserts** the six
reports exactly -- subject, sensor, type, lifecycle state, order and one shared
correlation id -- and only then removes them, so each test's own counts start
where they always did. Nothing is silently discarded: a missing, extra or
different startup report fails here.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from nova_perception_engine.domain.ports import OutboxRow

__all__ = ["STARTUP_REPORTS", "SUBJECT", "startup_reports_in", "take_startup_reports"]

SUBJECT = "perception.sensor.health_changed"

STARTUP_REPORTS: list[tuple[str, str, str]] = [
    ("voice-sensor-1", "voice", "initialized"),
    ("voice-sensor-1", "voice", "running"),
    ("camera-sensor-1", "camera", "initialized"),
    ("camera-sensor-1", "camera", "running"),
    ("companion-filesystem", "filesystem", "initialized"),
    ("companion-filesystem", "filesystem", "running"),
]
"""`main.py`'s startup order: voice, camera, filesystem; each initialized, then
running. `status` is the `SensorState` reached (A-4F7-2)."""


class _HasOutbox(Protocol):
    outbox: dict[UUID, OutboxRow]


def startup_reports_in(rows: list[OutboxRow]) -> list[tuple[str, str, str]]:
    return [
        (row.payload["sensor_id"], row.payload["sensor_type"], row.payload["status"])
        for row in rows
        if row.subject == SUBJECT
    ]


def take_startup_reports(repository: _HasOutbox) -> None:
    rows = list(repository.outbox.values())
    assert startup_reports_in(rows) == STARTUP_REPORTS
    assert len(rows) == len(STARTUP_REPORTS), "startup enqueued something besides its reports"
    assert len({row.correlation_id for row in rows}) == 1
    for key in [key for key, row in repository.outbox.items() if row.subject == SUBJECT]:
        del repository.outbox[key]

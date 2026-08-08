from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from nova_eventbus_sdk import EventBus
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_service_kit.outbox import dispatch_ready_events


@dataclass
class _Row:
    id: UUID
    subject: str
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


class _FakeRepository:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows
        self.dispatched_ids: list[UUID] = []

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[_Row]:
        return self._rows[:limit]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.dispatched_ids.append(outbox_id)
        self._rows = [row for row in self._rows if row.id != outbox_id]


class _Counter:
    def __init__(self) -> None:
        self.calls: list[tuple[int, dict[str, str] | None]] = []

    def add(self, amount: int, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((amount, attributes))


@dataclass
class _Metrics:
    outbox_dispatched_total: _Counter


async def _connected_in_memory_bus() -> EventBus:
    bus = InMemoryEventBus()
    await bus.connect()
    return bus


async def test_dispatch_ready_events_publishes_and_marks_each_row() -> None:
    row = _Row(
        id=uuid4(), subject="memory.episodic.created", payload={"x": 1}, correlation_id=uuid4()
    )
    repository = _FakeRepository([row])
    bus = await _connected_in_memory_bus()

    received: list[str] = []

    async def handler(envelope: object) -> None:
        received.append(envelope.subject)  # type: ignore[attr-defined]

    await bus.subscribe("memory.episodic.created", handler)

    dispatched = await dispatch_ready_events(repository, bus, source_engine="memory-engine")

    assert dispatched == 1
    assert repository.dispatched_ids == [row.id]
    assert received == ["memory.episodic.created"]


async def test_dispatch_ready_events_records_metrics_per_subject() -> None:
    row = _Row(id=uuid4(), subject="memory.episodic.created", payload={}, correlation_id=uuid4())
    repository = _FakeRepository([row])
    bus = await _connected_in_memory_bus()
    metrics = _Metrics(outbox_dispatched_total=_Counter())

    await dispatch_ready_events(repository, bus, source_engine="memory-engine", metrics=metrics)

    assert metrics.outbox_dispatched_total.calls == [(1, {"subject": "memory.episodic.created"})]


async def test_dispatch_ready_events_returns_zero_when_nothing_ready() -> None:
    repository = _FakeRepository([])
    bus = await _connected_in_memory_bus()

    dispatched = await dispatch_ready_events(repository, bus, source_engine="memory-engine")

    assert dispatched == 0


async def test_dispatch_ready_events_respects_batch_size() -> None:
    rows = [
        _Row(id=uuid4(), subject="memory.episodic.created", payload={}, correlation_id=uuid4())
        for _ in range(3)
    ]
    repository = _FakeRepository(rows)
    bus = await _connected_in_memory_bus()

    dispatched = await dispatch_ready_events(
        repository, bus, source_engine="memory-engine", batch_size=2
    )

    assert dispatched == 2

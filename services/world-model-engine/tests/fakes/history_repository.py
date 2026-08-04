"""`FakeWorldHistoryRepository` -- an in-memory `domain.ports.
WorldHistoryRepository`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from uuid import UUID, uuid4

from nova_world_model_engine.domain.models import (
    ConflictLogEntry,
    ObjectStateHistoryEntry,
    Prediction,
    Snapshot,
)
from nova_world_model_engine.domain.ports import GraphWriteIntent, OutboxEvent, OutboxRow


@dataclass
class _OutboxRecord:
    id: UUID
    subject: str
    payload: dict
    correlation_id: UUID
    causation_id: UUID | None
    graph_write: GraphWriteIntent | None
    created_at: datetime
    graph_applied_at: datetime | None = None
    dispatched_at: datetime | None = None


class FakeWorldHistoryRepository:
    """Implements `domain.ports.WorldHistoryRepository` in memory. Every write
    that carries an `outbox_event` appends to `outbox` (mirroring the real
    transactional-outbox row), so tests can assert exactly what an operation
    would have enqueued, including its `graph_write` intent, without a real
    Postgres/Neo4j."""

    def __init__(self) -> None:
        self.history: list[ObjectStateHistoryEntry] = []
        self.snapshots: dict[UUID, Snapshot] = {}
        self.predictions: dict[UUID, Prediction] = {}
        self.conflicts: list[ConflictLogEntry] = []
        self.outbox: dict[UUID, _OutboxRecord] = {}
        self._history_id_seq = count(1)
        self._seq = count()

    def _record_outbox(self, event: OutboxEvent | None) -> UUID | None:
        if event is None:
            return None
        record_id = uuid4()
        self.outbox[record_id] = _OutboxRecord(
            id=record_id,
            subject=event.subject,
            payload=event.payload,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            graph_write=event.graph_write,
            created_at=datetime.now(UTC).replace(microsecond=next(self._seq)),
        )
        return record_id

    async def append_object_history(
        self, entry: ObjectStateHistoryEntry, *, outbox_event: OutboxEvent | None = None
    ) -> ObjectStateHistoryEntry:
        stored = entry.model_copy(update={"id": next(self._history_id_seq)})
        self.history.append(stored)
        self._record_outbox(outbox_event)
        return stored

    async def list_object_history(
        self,
        object_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[ObjectStateHistoryEntry]:
        results = [
            e
            for e in self.history
            if e.object_id == object_id
            and (since is None or e.changed_at >= since)
            and (until is None or e.changed_at <= until)
        ]
        results.sort(key=lambda e: e.changed_at, reverse=True)
        return results[:limit]

    async def list_recent_history_for_user(
        self, *, user_id: UUID, limit: int = 1000
    ) -> list[ObjectStateHistoryEntry]:
        results = [e for e in self.history if e.user_id == user_id]
        results.sort(key=lambda e: e.changed_at, reverse=True)
        return results[:limit]

    async def create_snapshot(self, snapshot: Snapshot) -> Snapshot:
        self.snapshots[snapshot.id] = snapshot
        return snapshot

    async def list_snapshots(self, *, user_id: UUID, limit: int = 50) -> list[Snapshot]:
        results = [s for s in self.snapshots.values() if s.user_id == user_id]
        results.sort(key=lambda s: s.taken_at, reverse=True)
        return results[:limit]

    async def create_prediction(
        self, prediction: Prediction, *, outbox_event: OutboxEvent | None = None
    ) -> Prediction:
        self.predictions[prediction.id] = prediction
        self._record_outbox(outbox_event)
        return prediction

    async def list_predictions(self, *, user_id: UUID, limit: int = 50) -> list[Prediction]:
        results = [p for p in self.predictions.values() if p.user_id == user_id]
        results.sort(key=lambda p: p.created_at, reverse=True)
        return results[:limit]

    async def log_conflict(self, entry: ConflictLogEntry) -> ConflictLogEntry:
        self.conflicts.append(entry)
        return entry

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        record_id = self._record_outbox(event)
        assert record_id is not None
        return record_id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = [
            r
            for r in self.outbox.values()
            if r.dispatched_at is None and (r.graph_write is None or r.graph_applied_at is not None)
        ]
        rows.sort(key=lambda r: r.created_at)
        return [_to_row(r) for r in rows[:limit]]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.outbox[outbox_id].dispatched_at = datetime.now(UTC)

    async def list_pending_graph_writes(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = [
            r
            for r in self.outbox.values()
            if r.graph_write is not None and r.graph_applied_at is None
        ]
        rows.sort(key=lambda r: r.created_at)
        return [_to_row(r) for r in rows[:limit]]

    async def mark_graph_applied(self, outbox_id: UUID) -> None:
        self.outbox[outbox_id].graph_applied_at = datetime.now(UTC)

    async def count_stale_pending_graph_writes(self, *, older_than: datetime) -> int:
        return len(
            [
                r
                for r in self.outbox.values()
                if r.graph_write is not None
                and r.graph_applied_at is None
                and r.created_at < older_than
            ]
        )


def _to_row(record: _OutboxRecord) -> OutboxRow:
    return OutboxRow(
        id=record.id,
        subject=record.subject,
        payload=record.payload,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        graph_write=record.graph_write,
    )

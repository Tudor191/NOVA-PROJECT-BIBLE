"""`FakeUsageRepository` -- an in-memory `domain.ports.UsageRepository`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from uuid import UUID, uuid4

from nova_ai_model_orchestration_engine.domain.models import Budget, UsageRecord
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent, OutboxRow


@dataclass
class _OutboxRecord:
    id: UUID
    subject: str
    payload: dict
    correlation_id: UUID
    causation_id: UUID | None
    created_at: datetime
    dispatched_at: datetime | None = None


class FakeUsageRepository:
    """Every write that carries an `outbox_event` appends to `outbox` (mirroring
    the real transactional-outbox row), so tests can assert exactly what an
    operation would have enqueued without a real Postgres."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []
        self.budgets: dict[tuple[str, str | None], Budget] = {}
        self.outbox: dict[UUID, _OutboxRecord] = {}
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
            created_at=datetime.now(UTC).replace(microsecond=next(self._seq)),
        )
        return record_id

    async def record_usage(
        self, record: UsageRecord, *, outbox_event: OutboxEvent | None = None
    ) -> UsageRecord:
        self.records.append(record)
        self._record_outbox(outbox_event)
        return record

    async def list_usage(
        self,
        *,
        model_id: UUID | None = None,
        requesting_engine: str | None = None,
        correlation_id: UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[UsageRecord]:
        results = list(self.records)
        if model_id is not None:
            results = [r for r in results if r.model_id == model_id]
        if requesting_engine is not None:
            results = [r for r in results if r.requesting_engine == requesting_engine]
        if correlation_id is not None:
            results = [r for r in results if r.correlation_id == correlation_id]
        if since is not None:
            results = [r for r in results if r.created_at >= since]
        if until is not None:
            results = [r for r in results if r.created_at <= until]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    async def spend_this_period(self, *, scope: str, scope_ref: str | None) -> float:
        return sum(r.estimated_cost for r in self.records)

    async def get_budget(self, *, scope: str, scope_ref: str | None) -> Budget | None:
        return self.budgets.get((scope, scope_ref))

    async def list_budgets(self) -> list[Budget]:
        return list(self.budgets.values())

    async def upsert_budget(self, budget: Budget) -> Budget:
        self.budgets[(budget.scope, budget.scope_ref)] = budget
        return budget

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        record_id = self._record_outbox(event)
        assert record_id is not None
        return record_id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        rows = [r for r in self.outbox.values() if r.dispatched_at is None]
        rows.sort(key=lambda r: r.created_at)
        return [_to_row(r) for r in rows[:limit]]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.outbox[outbox_id].dispatched_at = datetime.now(UTC)


def _to_row(record: _OutboxRecord) -> OutboxRow:
    return OutboxRow(
        id=record.id,
        subject=record.subject,
        payload=record.payload,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        created_at=record.created_at,
    )

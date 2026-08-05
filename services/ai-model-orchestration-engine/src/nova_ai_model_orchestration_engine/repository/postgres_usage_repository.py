"""`PostgresUsageRepository` -- implements `domain.ports.UsageRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-2a/00-ai-model-orchestration-engine.md §4.

`record_usage` enqueues its outbox row in the same transaction as the write,
the same transactional-outbox convention as `PostgresModelRegistryRepository`.
`spend_this_period` only supports `period == "monthly"` (the only value
`Budget.period`'s `Literal` allows -- design doc §4/§18) and sums
`usage_record.estimated_cost` since the start of the current calendar month.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_ai_model_orchestration_engine.domain.models import (
    Budget,
    PrivacyLevel,
    RoutingDecision,
    UsageRecord,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent, OutboxRow
from nova_ai_model_orchestration_engine.repository.models import (
    BudgetORM,
    OutboxEventORM,
    UsageRecordORM,
)

__all__ = ["PostgresUsageRepository"]


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


def _budget_to_domain(row: BudgetORM) -> Budget:
    return Budget(
        id=row.id,
        scope=row.scope,
        scope_ref=row.scope_ref,
        period=row.period,
        limit_amount=row.limit_amount,
        currency=row.currency,
        alert_threshold_pct=row.alert_threshold_pct,
    )


def _to_domain(row: UsageRecordORM) -> UsageRecord:
    return UsageRecord(
        id=row.id,
        correlation_id=row.correlation_id,
        requesting_engine=row.requesting_engine,
        provider=row.provider,
        model_id=row.model_id,
        routing_decision=RoutingDecision.model_validate(row.routing_decision),
        estimated_complexity=row.estimated_complexity,
        latency_ms=row.latency_ms,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        estimated_cost=row.estimated_cost,
        retry_count=row.retry_count,
        fallback_used=row.fallback_used,
        privacy_classification=PrivacyLevel(row.privacy_classification),
        outcome=row.outcome,
        created_at=row.created_at,
        schema_version=row.schema_version,
    )


class PostgresUsageRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record_usage(
        self, record: UsageRecord, *, outbox_event: OutboxEvent | None = None
    ) -> UsageRecord:
        async with self._session_factory() as session, session.begin():
            orm = UsageRecordORM(
                id=record.id,
                correlation_id=record.correlation_id,
                requesting_engine=record.requesting_engine,
                provider=record.provider,
                model_id=record.model_id,
                routing_decision=record.routing_decision.model_dump(mode="json"),
                estimated_complexity=record.estimated_complexity,
                latency_ms=record.latency_ms,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                estimated_cost=record.estimated_cost,
                retry_count=record.retry_count,
                fallback_used=record.fallback_used,
                privacy_classification=record.privacy_classification.value,
                outcome=record.outcome,
                schema_version=record.schema_version,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            return _to_domain(orm)

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
        async with self._session_factory() as session:
            stmt = select(UsageRecordORM).order_by(UsageRecordORM.created_at.desc()).limit(limit)
            if model_id is not None:
                stmt = stmt.where(UsageRecordORM.model_id == model_id)
            if requesting_engine is not None:
                stmt = stmt.where(UsageRecordORM.requesting_engine == requesting_engine)
            if correlation_id is not None:
                stmt = stmt.where(UsageRecordORM.correlation_id == correlation_id)
            if since is not None:
                stmt = stmt.where(UsageRecordORM.created_at >= since)
            if until is not None:
                stmt = stmt.where(UsageRecordORM.created_at <= until)
            rows = (await session.execute(stmt)).scalars().all()
            return [_to_domain(row) for row in rows]

    async def spend_this_period(self, *, scope: str, scope_ref: str | None) -> float:
        async with self._session_factory() as session:
            period_start = func.date_trunc("month", func.now())
            stmt = select(func.coalesce(func.sum(UsageRecordORM.estimated_cost), 0.0)).where(
                UsageRecordORM.created_at >= period_start
            )
            if scope == "provider" and scope_ref is not None:
                stmt = stmt.where(UsageRecordORM.provider == scope_ref)
            elif scope == "model" and scope_ref is not None:
                stmt = stmt.where(UsageRecordORM.model_id == UUID(scope_ref))
            result = await session.execute(stmt)
            return float(result.scalar_one())

    async def get_budget(self, *, scope: str, scope_ref: str | None) -> Budget | None:
        async with self._session_factory() as session:
            stmt = select(BudgetORM).where(BudgetORM.scope == scope)
            stmt = (
                stmt.where(BudgetORM.scope_ref == scope_ref)
                if scope_ref is not None
                else stmt.where(BudgetORM.scope_ref.is_(None))
            )
            row = (await session.execute(stmt)).scalars().first()
            return _budget_to_domain(row) if row is not None else None

    async def list_budgets(self) -> list[Budget]:
        async with self._session_factory() as session:
            rows = (await session.execute(select(BudgetORM))).scalars().all()
            return [_budget_to_domain(row) for row in rows]

    async def upsert_budget(self, budget: Budget) -> Budget:
        async with self._session_factory() as session, session.begin():
            stmt = select(BudgetORM).where(BudgetORM.scope == budget.scope)
            stmt = (
                stmt.where(BudgetORM.scope_ref == budget.scope_ref)
                if budget.scope_ref is not None
                else stmt.where(BudgetORM.scope_ref.is_(None))
            )
            existing = (await session.execute(stmt)).scalars().first()
            if existing is not None:
                existing.period = budget.period
                existing.limit_amount = budget.limit_amount
                existing.currency = budget.currency
                existing.alert_threshold_pct = budget.alert_threshold_pct
                await session.flush()
                return _budget_to_domain(existing)
            orm = BudgetORM(
                id=budget.id,
                scope=budget.scope,
                scope_ref=budget.scope_ref,
                period=budget.period,
                limit_amount=budget.limit_amount,
                currency=budget.currency,
                alert_threshold_pct=budget.alert_threshold_pct,
            )
            session.add(orm)
            await session.flush()
            return _budget_to_domain(orm)

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        async with self._session_factory() as session, session.begin():
            orm = _outbox_orm(event)
            session.add(orm)
            await session.flush()
            return orm.id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxEventORM)
                .where(OutboxEventORM.dispatched_at.is_(None))
                .order_by(OutboxEventORM.created_at)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                OutboxRow(
                    id=row.id,
                    subject=row.subject,
                    payload=row.payload,
                    correlation_id=row.correlation_id,
                    causation_id=row.causation_id,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(OutboxEventORM)
                .where(OutboxEventORM.id == outbox_id)
                .values(dispatched_at=func.now())
            )

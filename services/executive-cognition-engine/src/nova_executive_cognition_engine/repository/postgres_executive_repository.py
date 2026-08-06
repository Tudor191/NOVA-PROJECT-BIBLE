"""`PostgresExecutiveRepository` -- implements `domain.ports.ExecutiveRepository`
against SQLAlchemy async, per the schema in docs/design/phase-2c/
00-executive-cognition-engine.md §19.

`finalize_decision` persists an `ExecutiveDecisionTrace` and (optionally) an
outbox row in one transaction -- the same transactional-outbox convention
`PostgresReasoningRepository.finalize` (Phase 2B) already established. Every
other write is its own short transaction, since only the terminal write
needs atomicity with the outbox.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_executive_cognition_engine.domain.models import (
    ExecutiveDecisionTrace,
    ExecutiveOverrideAction,
    ExecutiveRequest,
    HumanOverrideRequest,
)
from nova_executive_cognition_engine.domain.ports import OutboxEvent, OutboxRow
from nova_executive_cognition_engine.repository.models import (
    ExecutiveDecisionORM,
    ExecutiveOutcomeReportORM,
    ExecutiveRequestORM,
    HumanOverrideORM,
    OutboxEventORM,
)

__all__ = ["PostgresExecutiveRepository"]


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


def _request_to_domain(row: ExecutiveRequestORM) -> ExecutiveRequest:
    return ExecutiveRequest(
        requesting_engine=row.requesting_engine,
        request_kind=row.request_kind,
        user_id=row.user_id,
        correlation_id=row.correlation_id,
        urgency=row.urgency,
        importance=row.importance,
        complexity=row.complexity,
        risk=row.risk,
        learning_value=row.learning_value,
        resource_cost=row.resource_cost,
        user_impact=row.user_impact,
        deadline=row.deadline,
        goal_id=row.goal_id,
        goal_tier=row.goal_tier,
    )


def _trace_to_domain(row: ExecutiveDecisionORM) -> ExecutiveDecisionTrace:
    return ExecutiveDecisionTrace.model_validate(row.trace_payload)


def _requesting_engine_for(trace: ExecutiveDecisionTrace) -> str:
    for contender in trace.contending_requests:
        if contender.correlation_id == trace.correlation_id:
            return contender.requesting_engine
    return trace.contending_requests[0].requesting_engine if trace.contending_requests else ""


class PostgresExecutiveRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record_request(self, request: ExecutiveRequest) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ExecutiveRequestORM(
                    correlation_id=request.correlation_id,
                    requesting_engine=request.requesting_engine,
                    request_kind=request.request_kind,
                    user_id=request.user_id,
                    urgency=request.urgency,
                    importance=request.importance,
                    complexity=request.complexity,
                    risk=request.risk,
                    learning_value=request.learning_value,
                    resource_cost=request.resource_cost,
                    user_impact=request.user_impact,
                    deadline=request.deadline,
                    goal_id=request.goal_id,
                    goal_tier=request.goal_tier,
                )
            )

    async def requests_for_goal(
        self, goal_id: UUID, *, exclude_correlation_id: UUID | None = None, limit: int = 20
    ) -> list[ExecutiveRequest]:
        async with self._session_factory() as session:
            stmt = (
                select(ExecutiveRequestORM)
                .where(ExecutiveRequestORM.goal_id == goal_id)
                .order_by(ExecutiveRequestORM.created_at.desc())
                .limit(limit)
            )
            if exclude_correlation_id is not None:
                stmt = stmt.where(ExecutiveRequestORM.correlation_id != exclude_correlation_id)
            rows = (await session.execute(stmt)).scalars().all()
            return [_request_to_domain(row) for row in rows]

    async def finalize_decision(
        self,
        *,
        trace: ExecutiveDecisionTrace,
        outbox_event: OutboxEvent | None = None,
    ) -> ExecutiveDecisionTrace:
        async with self._session_factory() as session, session.begin():
            session.add(
                ExecutiveDecisionORM(
                    id=trace.id,
                    correlation_id=trace.correlation_id,
                    requesting_engine=_requesting_engine_for(trace),
                    decision_type=trace.decision_type.value,
                    outcome=trace.outcome.value,
                    trace_payload=trace.model_dump(mode="json"),
                    schema_version=trace.schema_version,
                )
            )
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            return trace

    async def get_decision(self, decision_id: UUID) -> ExecutiveDecisionTrace | None:
        async with self._session_factory() as session:
            row = await session.get(ExecutiveDecisionORM, decision_id)
            return _trace_to_domain(row) if row is not None else None

    async def list_decisions(
        self, *, requesting_engine: str | None = None, limit: int = 100
    ) -> list[ExecutiveDecisionTrace]:
        async with self._session_factory() as session:
            stmt = (
                select(ExecutiveDecisionORM)
                .order_by(ExecutiveDecisionORM.created_at.desc())
                .limit(limit)
            )
            if requesting_engine is not None:
                stmt = stmt.where(ExecutiveDecisionORM.requesting_engine == requesting_engine)
            rows = (await session.execute(stmt)).scalars().all()
            return [_trace_to_domain(row) for row in rows]

    async def record_outcome_report(
        self,
        *,
        correlation_id: UUID,
        outcome: str,
        actual_duration_ms: float | None,
        note: str | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ExecutiveOutcomeReportORM(
                    correlation_id=correlation_id,
                    outcome=outcome,
                    actual_duration_ms=actual_duration_ms,
                    note=note,
                )
            )

    async def apply_override(
        self,
        decision_id: UUID,
        override: HumanOverrideRequest,
        *,
        outbox_event: OutboxEvent | None = None,
    ) -> ExecutiveDecisionTrace:
        async with self._session_factory() as session, session.begin():
            row = await session.get(ExecutiveDecisionORM, decision_id)
            if row is None:
                raise LookupError(f"No decision found with id {decision_id!r}")
            trace = _trace_to_domain(row)
            trace.human_override = override
            if override.action == ExecutiveOverrideAction.REDIRECT and (
                override.redirect_outcome is not None
            ):
                # §13: "redirect records the user's chosen outcome in place of
                # this engine's own" -- never presented as if the Priority
                # Matrix itself had chosen it (ADR-028); `human_override` on
                # the trace is what makes this a recorded correction.
                trace.outcome = override.redirect_outcome
            row.trace_payload = trace.model_dump(mode="json")
            row.outcome = trace.outcome.value
            session.add(
                HumanOverrideORM(
                    executive_decision_id=override.executive_decision_id,
                    action=override.action.value,
                    redirect_outcome=(
                        override.redirect_outcome.value
                        if override.redirect_outcome is not None
                        else None
                    ),
                    note=override.note,
                )
            )
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            return trace

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

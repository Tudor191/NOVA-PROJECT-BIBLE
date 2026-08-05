"""`PostgresReasoningRepository` -- implements `domain.ports.ReasoningRepository`
against SQLAlchemy async, per the schema in docs/design/phase-2b/
00-reasoning-engine.md §20.

`finalize` persists a `Decision`, its `ReasoningTrace`, the process's
terminal status, and (optionally) an outbox row all in one transaction --
the same transactional-outbox convention `PostgresUsageRepository` (Phase
2A) already established. Every other write is its own short transaction,
since only the terminal write needs atomicity with the outbox.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_reasoning_engine.domain.models import (
    Alternative,
    Decision,
    DecisionExplanation,
    Evidence,
    HumanOverrideRequest,
    Hypothesis,
    LifecycleStatus,
    ReasoningProcess,
    ReasoningTrace,
)
from nova_reasoning_engine.domain.ports import OutboxEvent, OutboxRow
from nova_reasoning_engine.repository.models import (
    AlternativeORM,
    DecisionORM,
    EvidenceORM,
    HypothesisORM,
    OutboxEventORM,
    ReasoningProcessORM,
    ReasoningTraceORM,
)

__all__ = ["PostgresReasoningRepository"]


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


def _process_to_domain(row: ReasoningProcessORM) -> ReasoningProcess:
    return ReasoningProcess(
        id=row.id,
        correlation_id=row.correlation_id,
        requesting_engine=row.requesting_engine,
        user_id=row.user_id,
        parent_process_id=row.parent_process_id,
        objective_text=row.objective_text,
        reasoning_mode=row.reasoning_mode,
        reasoning_level=row.reasoning_level,
        status=row.status,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def _decision_to_domain(row: DecisionORM) -> Decision:
    return Decision(
        id=row.id,
        reasoning_process_id=row.reasoning_process_id,
        selected_alternative_id=row.selected_alternative_id,
        explanation=DecisionExplanation.model_validate(row.explanation),
        confidence_score=row.confidence_score,
        human_override=(
            HumanOverrideRequest.model_validate(row.human_override)
            if row.human_override is not None
            else None
        ),
    )


def _trace_to_domain(row: ReasoningTraceORM) -> ReasoningTrace:
    return ReasoningTrace.model_validate(row.trace_payload)


class PostgresReasoningRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_process(self, process: ReasoningProcess) -> ReasoningProcess:
        async with self._session_factory() as session, session.begin():
            orm = ReasoningProcessORM(
                id=process.id,
                correlation_id=process.correlation_id,
                requesting_engine=process.requesting_engine,
                user_id=process.user_id,
                parent_process_id=process.parent_process_id,
                objective_text=process.objective_text,
                reasoning_mode=process.reasoning_mode.value,
                reasoning_level=process.reasoning_level,
                status=process.status,
            )
            session.add(orm)
            await session.flush()
            return _process_to_domain(orm)

    async def transition_process(
        self,
        process_id: UUID,
        *,
        status: LifecycleStatus,
        completed_at: datetime | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            values: dict[str, object] = {"status": status}
            if completed_at is not None:
                values["completed_at"] = completed_at
            await session.execute(
                update(ReasoningProcessORM)
                .where(ReasoningProcessORM.id == process_id)
                .values(**values)
            )

    async def get_process(self, process_id: UUID) -> ReasoningProcess | None:
        async with self._session_factory() as session:
            row = await session.get(ReasoningProcessORM, process_id)
            return _process_to_domain(row) if row is not None else None

    async def record_hypotheses(self, hypotheses: list[Hypothesis]) -> None:
        if not hypotheses:
            return
        async with self._session_factory() as session, session.begin():
            session.add_all(
                HypothesisORM(
                    id=h.id,
                    reasoning_process_id=h.reasoning_process_id,
                    description=h.description,
                    status=h.status,
                )
                for h in hypotheses
            )

    async def update_hypothesis_status(
        self, hypothesis_id: UUID, *, status: Literal["investigating", "supported", "unsupported"]
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(HypothesisORM).where(HypothesisORM.id == hypothesis_id).values(status=status)
            )

    async def record_evidence(self, evidence: list[Evidence]) -> None:
        if not evidence:
            return
        async with self._session_factory() as session, session.begin():
            session.add_all(
                EvidenceORM(
                    id=e.id,
                    hypothesis_id=e.hypothesis_id,
                    source=e.source,
                    source_ref=e.source_ref,
                    weight=e.weight,
                )
                for e in evidence
            )

    async def record_alternatives(self, alternatives: list[Alternative]) -> None:
        if not alternatives:
            return
        async with self._session_factory() as session, session.begin():
            session.add_all(
                AlternativeORM(
                    id=a.id,
                    reasoning_process_id=a.reasoning_process_id,
                    hypothesis_id=a.hypothesis_id,
                    description=a.description,
                    constraint_status=a.constraint_status,
                    matrix_scores=(
                        a.matrix_scores.model_dump(mode="json")
                        if a.matrix_scores is not None
                        else None
                    ),
                )
                for a in alternatives
            )

    async def finalize(
        self,
        *,
        process: ReasoningProcess,
        decision: Decision,
        trace: ReasoningTrace,
        outbox_event: OutboxEvent | None = None,
    ) -> Decision:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(ReasoningProcessORM)
                .where(ReasoningProcessORM.id == process.id)
                .values(status=process.status, completed_at=process.completed_at)
            )
            decision_orm = DecisionORM(
                id=decision.id,
                reasoning_process_id=decision.reasoning_process_id,
                selected_alternative_id=decision.selected_alternative_id,
                explanation=decision.explanation.model_dump(mode="json"),
                confidence_score=decision.confidence_score,
                human_override=(
                    decision.human_override.model_dump(mode="json")
                    if decision.human_override is not None
                    else None
                ),
            )
            session.add(decision_orm)
            trace_orm = ReasoningTraceORM(
                id=trace.id,
                reasoning_process_id=trace.reasoning_process_id,
                trace_payload=trace.model_dump(mode="json"),
                schema_version=trace.schema_version,
            )
            session.add(trace_orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            return _decision_to_domain(decision_orm)

    async def get_decision(self, decision_id: UUID) -> Decision | None:
        async with self._session_factory() as session:
            row = await session.get(DecisionORM, decision_id)
            return _decision_to_domain(row) if row is not None else None

    async def get_decision_for_process(self, reasoning_process_id: UUID) -> Decision | None:
        async with self._session_factory() as session:
            stmt = select(DecisionORM).where(
                DecisionORM.reasoning_process_id == reasoning_process_id
            )
            row = (await session.execute(stmt)).scalars().first()
            return _decision_to_domain(row) if row is not None else None

    async def get_trace(self, trace_id: UUID) -> ReasoningTrace | None:
        async with self._session_factory() as session:
            row = await session.get(ReasoningTraceORM, trace_id)
            return _trace_to_domain(row) if row is not None else None

    async def get_trace_for_process(self, reasoning_process_id: UUID) -> ReasoningTrace | None:
        async with self._session_factory() as session:
            stmt = select(ReasoningTraceORM).where(
                ReasoningTraceORM.reasoning_process_id == reasoning_process_id
            )
            row = (await session.execute(stmt)).scalars().first()
            return _trace_to_domain(row) if row is not None else None

    async def list_traces(
        self, *, user_id: UUID | None = None, limit: int = 100
    ) -> list[ReasoningTrace]:
        async with self._session_factory() as session:
            stmt = select(ReasoningTraceORM).order_by(ReasoningTraceORM.created_at.desc()).limit(
                limit
            )
            if user_id is not None:
                stmt = stmt.join(
                    ReasoningProcessORM,
                    ReasoningProcessORM.id == ReasoningTraceORM.reasoning_process_id,
                ).where(ReasoningProcessORM.user_id == user_id)
            rows = (await session.execute(stmt)).scalars().all()
            return [_trace_to_domain(row) for row in rows]

    async def apply_override(
        self,
        decision_id: UUID,
        override: HumanOverrideRequest,
        *,
        outbox_event: OutboxEvent | None = None,
    ) -> Decision:
        async with self._session_factory() as session, session.begin():
            row = await session.get(DecisionORM, decision_id)
            if row is None:
                raise LookupError(f"No decision found with id {decision_id!r}")
            row.human_override = override.model_dump(mode="json")
            if override.action == "redirect" and override.redirect_alternative_id is not None:
                # §18: "redirect re-scores with the user-selected alternative forced to
                # the top" -- Phase 2B applies this narrowly, updating which alternative
                # is selected without re-deriving matrix scores or explanation text this
                # engine no longer has the original Alternative row's inputs to redo
                # honestly; `human_override` on the row is what makes this a recorded
                # correction, never presented as if the matrix itself had chosen it.
                row.selected_alternative_id = override.redirect_alternative_id
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            return _decision_to_domain(row)

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

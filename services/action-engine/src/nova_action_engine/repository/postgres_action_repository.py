"""`PostgresActionRepository` -- implements `domain.ports.ActionRepository`
against SQLAlchemy async, per the schema in
docs/design/phase-3/07-tdd-3d-action-engine.md §8.

`insert()` translates an `id` primary-key violation (`sqlalchemy.exc.IntegrityError`)
into `ActionAlreadyExistsError` -- the natural-key idempotency guard
approved for `action.execute` (§5.3, `13-3d-action-engine-research.md`),
mirroring `capability-engine`'s own `CapabilityAlreadyExistsError`/Fork
3C-4 translation exactly.

**`depends_on` is stored as JSONB strings, not `UUID` objects.**
`Action.depends_on` is a `list[UUID]`; `action.action.depends_on` is a JSONB
column, and the JSON encoder asyncpg drives has no `UUID` serializer --
inserting the objects raised `TypeError: Object of type UUID is not JSON
serializable` for every Action carrying a dependency, which is exactly
`coding-agent`'s `git add`/`git commit` steps (decision D5). `insert()`
therefore writes `str(uuid)` and `_to_domain()` parses back with `UUID(...)`,
so the round trip returns the same `list[UUID]` the caller passed. Nothing
about the public contract or the schema changes: `Action.depends_on` is
still `list[UUID]` to every caller, and the column is still JSONB. The
symmetric `str()`/`UUID()` pair is deliberate -- a bare `list(...)` on read
would silently hand callers `list[str]` for rows written by any other
writer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from nova_contracts import Action, RetryPolicy, RollbackStrategy
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_action_engine.domain.models import IdentityConfidencePolicy, PendingApproval
from nova_action_engine.domain.ports import ActionAlreadyExistsError
from nova_action_engine.repository.models import (
    ActionExecutionHistoryORM,
    ActionORM,
    IdentityConfidencePolicyORM,
    PendingApprovalORM,
)

__all__ = ["PostgresActionRepository"]


def _to_domain(row: ActionORM) -> Action:
    return Action(
        id=row.id,
        action_type=row.action_type,
        priority=row.priority,
        source=row.source,
        requested_by=row.requested_by,
        execution_target=row.execution_target,
        depends_on=[UUID(value) for value in row.depends_on],
        parameters=dict(row.parameters),
        expected_result=row.expected_result,
        risk=row.risk,
        timeout_seconds=row.timeout_seconds,
        retry_policy=RetryPolicy.model_validate(row.retry_policy),
        rollback_strategy=(
            RollbackStrategy.model_validate(row.rollback_strategy)
            if row.rollback_strategy is not None
            else None
        ),
        required_permissions=list(row.required_permissions),
        status=row.status,
        verification_method=row.verification_method,
        confidence=row.confidence,
    )


class PostgresActionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_id(self, action_id: UUID) -> Action | None:
        async with self._session_factory() as session:
            row = await session.get(ActionORM, action_id)
            return _to_domain(row) if row is not None else None

    async def insert(self, action: Action) -> Action:
        row = ActionORM(
            id=action.id,
            action_type=action.action_type,
            priority=action.priority,
            source=action.source,
            requested_by=action.requested_by,
            execution_target=action.execution_target,
            depends_on=[str(dependency) for dependency in action.depends_on],
            parameters=dict(action.parameters),
            expected_result=action.expected_result,
            risk=action.risk,
            timeout_seconds=action.timeout_seconds,
            retry_policy=action.retry_policy.model_dump(mode="json"),
            rollback_strategy=(
                action.rollback_strategy.model_dump(mode="json")
                if action.rollback_strategy is not None
                else None
            ),
            required_permissions=list(action.required_permissions),
            status=action.status,
            verification_method=action.verification_method,
            confidence=action.confidence,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ActionAlreadyExistsError(f"action {action.id} already exists") from exc
        return action

    async def update_status(
        self, action_id: UUID, *, status: str, confidence: float | None = None
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(ActionORM, action_id)
            if row is None:
                return
            row.status = status
            if confidence is not None:
                row.confidence = confidence
            await session.commit()

    async def record_result(
        self, action_id: UUID, *, result: dict | None, error: str | None
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(ActionORM, action_id)
            if row is None:
                return
            row.result = result
            row.error = error
            await session.commit()

    async def get_result(self, action_id: UUID) -> tuple[dict | None, str | None] | None:
        async with self._session_factory() as session:
            row = await session.get(ActionORM, action_id)
            if row is None:
                return None
            if row.result is None and row.error is None:
                # Ambiguous with a legitimately-recorded "no result, no
                # error" terminal state (e.g. a denied action) -- harmless
                # in the one call site (`_idempotent_reply_if_terminal`),
                # which falls back to the same `(None, None)` regardless.
                return None
            return dict(row.result) if row.result is not None else None, row.error

    async def insert_pending_approval(self, approval: PendingApproval) -> None:
        async with self._session_factory() as session:
            session.add(
                PendingApprovalORM(
                    action_id=approval.action_id,
                    risk=approval.risk,
                    requested_at=approval.requested_at,
                    decided_at=approval.decided_at,
                    decision=approval.decision,
                )
            )
            await session.commit()

    async def find_pending_approval(self, action_id: UUID) -> PendingApproval | None:
        async with self._session_factory() as session:
            row = await session.get(PendingApprovalORM, action_id)
            if row is None:
                return None
            return PendingApproval(
                action_id=row.action_id,
                risk=row.risk,
                requested_at=row.requested_at,
                decided_at=row.decided_at,
                decision=row.decision,
            )

    async def list_pending_approvals(self, *, limit: int = 50) -> list[PendingApproval]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PendingApprovalORM)
                .where(PendingApprovalORM.decision.is_(None))
                .order_by(PendingApprovalORM.requested_at)
                .limit(limit)
            )
            return [
                PendingApproval(
                    action_id=row.action_id,
                    risk=row.risk,
                    requested_at=row.requested_at,
                    decided_at=row.decided_at,
                    decision=row.decision,
                )
                for row in result.scalars().all()
            ]

    async def decide_pending_approval(
        self, action_id: UUID, *, decision: Literal["approved", "denied"], decided_at: datetime
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(PendingApprovalORM, action_id)
            if row is None:
                return
            row.decision = decision
            row.decided_at = decided_at
            await session.commit()

    async def record_execution_history(
        self, *, action_id: UUID, stage: str, outcome: str, detail: str | None = None
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                ActionExecutionHistoryORM(
                    action_id=action_id, stage=stage, outcome=outcome, detail=detail
                )
            )
            await session.commit()

    async def find_identity_confidence_policy(
        self, user_id: UUID
    ) -> IdentityConfidencePolicy | None:
        async with self._session_factory() as session:
            row = await session.get(IdentityConfidencePolicyORM, user_id)
            if row is None:
                return None
            return IdentityConfidencePolicy(
                user_id=row.user_id,
                minimum_confidence_by_risk=dict(row.minimum_confidence_by_risk),
            )

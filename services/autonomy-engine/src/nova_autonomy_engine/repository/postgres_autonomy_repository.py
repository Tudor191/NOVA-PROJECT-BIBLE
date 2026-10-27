"""`AutonomyRepository` over Postgres -- TDD 4D §9.

**One logical operation, one transaction, one commit** (decision D-3, as 4C.2
applied it). Every public method opens exactly one `session.begin()` block, and
the two methods that write coupled rows -- `insert_suggestion` and
`decide_suggestion` -- write both rows inside that single block.

**The decision log is append-only.** There is no `update_decision_log`, no
`delete_decision_log`, and no truncate. `domain/ports.py`'s
`FORBIDDEN_REPOSITORY_METHODS` lists the names, and
`tests/unit/test_repository_contract.py` asserts their absence from this class
mechanically rather than by review.

**Keyset pagination, never offset.** `list_suggestions` seeks on
`(created_at, id)` against an index of the same shape. The cursor is opaque
(base64 of the two keys) so no caller can reconstruct an offset from it, and a
malformed cursor is rejected rather than silently treated as "start from the
beginning" -- which would turn a client bug into a silent duplicate page.

**Row ordering is designed out, not discovered.** `insert_suggestion` calls
`flush()` between the parent and the child even though `SuggestionORM.decisions`
already declares the relationship, because 4C.2's `4eafa80` defect is the
reason this engine has a `real_infra` tier at all: source inspection and a fake
repository cannot exercise a foreign key. Belt and braces, deliberately.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    AutonomyLevelSetting,
    DecisionLogEntry,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyCheck,
    PolicyEffect,
    PolicyMatch,
    RiskLevel,
    Suggestion,
    SuggestionStatus,
)
from nova_autonomy_engine.domain.ports import (
    SuggestionAlreadyDecidedError,
    SuggestionNotFoundError,
    SuggestionPage,
)
from nova_autonomy_engine.repository.cursor import decode_cursor, encode_cursor
from nova_autonomy_engine.repository.models import (
    AutonomyLevelORM,
    DecisionLogORM,
    PermissionGrantORM,
    PolicyORM,
    SuggestionORM,
)

__all__ = ["PostgresAutonomyRepository"]


def _policy_to_domain(row: PolicyORM) -> Policy:
    return Policy(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        effect=PolicyEffect(row.effect),
        match=PolicyMatch(
            category=(
                PermissionCategory(row.match_category) if row.match_category is not None else None
            ),
            min_risk=RiskLevel(row.match_min_risk) if row.match_min_risk is not None else None,
            capability_class=row.match_capability_class,
        ),
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _grant_to_domain(row: PermissionGrantORM) -> PermissionGrant:
    return PermissionGrant(
        user_id=row.user_id,
        category=PermissionCategory(row.category),
        max_risk=RiskLevel(row.max_risk) if row.max_risk is not None else None,
        requires_approval_above=(
            RiskLevel(row.requires_approval_above)
            if row.requires_approval_above is not None
            else None
        ),
        updated_at=row.updated_at,
    )


def _suggestion_to_domain(row: SuggestionORM) -> Suggestion:
    return Suggestion(
        id=row.id,
        user_id=row.user_id,
        category=PermissionCategory(row.category),
        risk=RiskLevel(row.risk),
        title=row.title,
        detail=row.detail,
        status=SuggestionStatus(row.status),
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


def _log_to_domain(row: DecisionLogORM) -> DecisionLogEntry:
    return DecisionLogEntry(
        id=row.id,
        subject_id=row.action_id,
        autonomy_level=AutonomyLevel(row.autonomy_level),
        risk=RiskLevel(row.risk),
        confidence=row.confidence,
        policy_checks=[PolicyCheck.model_validate(check) for check in row.policy_checks],
        outcome=row.outcome,
        reason=row.reason,
        created_at=row.created_at,
    )


def _log_to_orm(entry: DecisionLogEntry, *, suggestion_id: UUID | None) -> DecisionLogORM:
    return DecisionLogORM(
        id=entry.id,
        action_id=entry.subject_id,
        suggestion_id=suggestion_id,
        autonomy_level=int(entry.autonomy_level),
        risk=entry.risk.value,
        confidence=entry.confidence,
        policy_checks=[check.model_dump(mode="json") for check in entry.policy_checks],
        outcome=entry.outcome.value if entry.outcome is not None else None,
        reason=entry.reason,
        created_at=entry.created_at,
    )


class PostgresAutonomyRepository:
    """The shipped `AutonomyRepository`. Takes a session factory rather than an
    engine so the `real_infra` tier can bind it to a transaction-scoped session
    without this class knowing anything about the test harness."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # --- Autonomy level -------------------------------------------------
    async def get_level(self, user_id: UUID) -> AutonomyLevelSetting | None:
        async with self._session_factory() as session:
            row = await session.get(AutonomyLevelORM, user_id)
            if row is None:
                return None
            return AutonomyLevelSetting(
                user_id=row.user_id, level=AutonomyLevel(row.level), updated_at=row.updated_at
            )

    async def set_level(self, user_id: UUID, level: AutonomyLevel) -> AutonomyLevelSetting:
        async with self._session_factory() as session, session.begin():
            row = await session.get(AutonomyLevelORM, user_id)
            moment = datetime.now(UTC)
            if row is None:
                row = AutonomyLevelORM(user_id=user_id, level=int(level), updated_at=moment)
                session.add(row)
            else:
                row.level = int(level)
                row.updated_at = moment
            return AutonomyLevelSetting(user_id=user_id, level=level, updated_at=moment)

    # --- Policies -------------------------------------------------------
    async def list_policies(self, user_id: UUID) -> list[Policy]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PolicyORM)
                .where(PolicyORM.user_id == user_id)
                .order_by(PolicyORM.created_at, PolicyORM.id)
            )
            return [_policy_to_domain(row) for row in result.scalars()]

    async def get_policy(self, user_id: UUID, policy_id: UUID) -> Policy | None:
        async with self._session_factory() as session:
            row = await session.get(PolicyORM, policy_id)
            if row is None or row.user_id != user_id:
                return None
            return _policy_to_domain(row)

    async def create_policy(self, policy: Policy) -> Policy:
        async with self._session_factory() as session, session.begin():
            session.add(
                PolicyORM(
                    id=policy.id,
                    user_id=policy.user_id,
                    name=policy.name,
                    effect=policy.effect.value,
                    match_category=(
                        policy.match.category.value if policy.match.category is not None else None
                    ),
                    match_min_risk=(
                        policy.match.min_risk.value if policy.match.min_risk is not None else None
                    ),
                    match_capability_class=policy.match.capability_class,
                    enabled=policy.enabled,
                    created_at=policy.created_at,
                    updated_at=policy.updated_at,
                )
            )
        return policy

    async def replace_policy(self, policy: Policy) -> Policy | None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(PolicyORM, policy.id)
            if row is None or row.user_id != policy.user_id:
                return None
            row.name = policy.name
            row.effect = policy.effect.value
            row.match_category = (
                policy.match.category.value if policy.match.category is not None else None
            )
            row.match_min_risk = (
                policy.match.min_risk.value if policy.match.min_risk is not None else None
            )
            row.match_capability_class = policy.match.capability_class
            row.enabled = policy.enabled
            row.updated_at = datetime.now(UTC)
            updated = policy.model_copy(update={"updated_at": row.updated_at})
        return updated

    async def delete_policy(self, user_id: UUID, policy_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                delete(PolicyORM).where(PolicyORM.id == policy_id, PolicyORM.user_id == user_id)
            )
            return bool(cast(CursorResult, result).rowcount)

    # --- Permission matrix ----------------------------------------------
    async def list_permission_grants(self, user_id: UUID) -> list[PermissionGrant]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PermissionGrantORM).where(PermissionGrantORM.user_id == user_id)
            )
            return [_grant_to_domain(row) for row in result.scalars()]

    async def upsert_permission_grants(
        self, user_id: UUID, grants: list[PermissionGrant]
    ) -> list[PermissionGrant]:
        """Upserts **only the categories named**. Categories left out keep the
        rows they had -- never reset to a permissive default, which is how a
        partial write would widen authority."""
        moment = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            for grant in grants:
                row = await session.get(PermissionGrantORM, (user_id, grant.category.value))
                if row is None:
                    session.add(
                        PermissionGrantORM(
                            user_id=user_id,
                            category=grant.category.value,
                            max_risk=grant.max_risk.value if grant.max_risk is not None else None,
                            requires_approval_above=(
                                grant.requires_approval_above.value
                                if grant.requires_approval_above is not None
                                else None
                            ),
                            updated_at=moment,
                        )
                    )
                else:
                    row.max_risk = grant.max_risk.value if grant.max_risk is not None else None
                    row.requires_approval_above = (
                        grant.requires_approval_above.value
                        if grant.requires_approval_above is not None
                        else None
                    )
                    row.updated_at = moment
        return await self.list_permission_grants(user_id)

    # --- Suggestions ----------------------------------------------------
    async def insert_suggestion(
        self, suggestion: Suggestion, log_entry: DecisionLogEntry
    ) -> Suggestion:
        """Parent then child, **one transaction**. The `flush()` between them
        is the 4C.2 lesson made explicit: it forces the suggestion INSERT to
        reach the database before the log row that references it, regardless of
        how SQLAlchemy would otherwise order two mappers within the flush."""
        async with self._session_factory() as session, session.begin():
            session.add(
                SuggestionORM(
                    id=suggestion.id,
                    user_id=suggestion.user_id,
                    category=suggestion.category.value,
                    risk=suggestion.risk.value,
                    title=suggestion.title,
                    detail=suggestion.detail,
                    status=suggestion.status.value,
                    created_at=suggestion.created_at,
                    decided_at=suggestion.decided_at,
                )
            )
            await session.flush()
            session.add(_log_to_orm(log_entry, suggestion_id=suggestion.id))
        return suggestion

    async def list_suggestions(
        self,
        user_id: UUID,
        *,
        status: SuggestionStatus | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> SuggestionPage:
        statement = select(SuggestionORM).where(SuggestionORM.user_id == user_id)
        if status is not None:
            statement = statement.where(SuggestionORM.status == status.value)
        if cursor is not None:
            after_created_at, after_id = decode_cursor(cursor)
            # Strict keyset seek on the composite key, matching
            # ix_suggestion_user_created_id. No OFFSET is constructible from a
            # cursor, which is the point (TDD §8.1/§9).
            statement = statement.where(
                (SuggestionORM.created_at < after_created_at)
                | ((SuggestionORM.created_at == after_created_at) & (SuggestionORM.id < after_id))
            )
        statement = statement.order_by(
            SuggestionORM.created_at.desc(), SuggestionORM.id.desc()
        ).limit(limit + 1)

        async with self._session_factory() as session:
            result = await session.execute(statement)
            rows = list(result.scalars())

        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = (
            encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
        )
        return SuggestionPage(
            items=[_suggestion_to_domain(row) for row in page], next_cursor=next_cursor
        )

    async def get_suggestion(self, user_id: UUID, suggestion_id: UUID) -> Suggestion | None:
        async with self._session_factory() as session:
            row = await session.get(SuggestionORM, suggestion_id)
            if row is None or row.user_id != user_id:
                return None
            return _suggestion_to_domain(row)

    async def decide_suggestion(
        self,
        user_id: UUID,
        suggestion_id: UUID,
        *,
        status: SuggestionStatus,
        log_entry: DecisionLogEntry,
    ) -> Suggestion:
        """The AC-5 transition, **one transaction**.

        The status change is a **conditional UPDATE** -- `WHERE status =
        'proposed'` -- not a read followed by a write. A check-then-write would
        let two concurrent approvals both observe `proposed` and both succeed;
        this way exactly one UPDATE reports a row, and the loser gets the 409
        TDD §13 requires.
        """
        moment = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(SuggestionORM)
                .where(
                    SuggestionORM.id == suggestion_id,
                    SuggestionORM.user_id == user_id,
                    SuggestionORM.status == SuggestionStatus.PROPOSED.value,
                )
                .values(status=status.value, decided_at=moment)
            )
            if not cast(CursorResult, result).rowcount:
                existing = await session.get(SuggestionORM, suggestion_id)
                if existing is None or existing.user_id != user_id:
                    raise SuggestionNotFoundError(
                        f"no suggestion {suggestion_id} for this user"
                    )
                raise SuggestionAlreadyDecidedError(
                    suggestion_id, SuggestionStatus(existing.status)
                )
            session.add(_log_to_orm(log_entry, suggestion_id=suggestion_id))
            row = await session.get(SuggestionORM, suggestion_id)
            assert row is not None  # noqa: S101 - the UPDATE above just matched it
            decided = _suggestion_to_domain(row)
        return decided

    # --- Decision log (append-only: no update, no delete) ---------------
    async def append_decision_log(self, entry: DecisionLogEntry) -> DecisionLogEntry:
        """For decisions that produced no suggestion -- a `deny` or an
        `observe_only`. `suggestion_id` stays `NULL`; doc 07's `action_id`
        carries the decision's own subject id either way."""
        async with self._session_factory() as session, session.begin():
            session.add(_log_to_orm(entry, suggestion_id=None))
        return entry

    async def list_decision_log(
        self, *, subject_id: UUID | None = None, limit: int = 50
    ) -> list[DecisionLogEntry]:
        statement = select(DecisionLogORM)
        if subject_id is not None:
            statement = statement.where(DecisionLogORM.action_id == subject_id)
        statement = statement.order_by(
            DecisionLogORM.created_at.desc(), DecisionLogORM.id.desc()
        ).limit(limit)
        async with self._session_factory() as session:
            result = await session.execute(statement)
            return [_log_to_domain(row) for row in result.scalars()]

    async def count_suggestions(
        self, user_id: UUID, *, status: SuggestionStatus | None = None
    ) -> int:
        statement = (
            select(func.count())
            .select_from(SuggestionORM)
            .where(SuggestionORM.user_id == user_id)
        )
        if status is not None:
            statement = statement.where(SuggestionORM.status == status.value)
        async with self._session_factory() as session:
            result = await session.execute(statement)
            return int(result.scalar_one())

    async def ping(self) -> None:
        """Raises on an unusable connection, so `/internal/readiness` reports
        **not ready** rather than a healthy-looking success (TDD §16 control
        12)."""
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

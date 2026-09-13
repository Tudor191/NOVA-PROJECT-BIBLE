"""In-memory `AutonomyRepository` for the default (no-Docker) tier.

**It mirrors the Postgres repository's *semantics*, and cannot substitute for
its *constraints*.** A fake dictionary has no foreign key, so the coupling
between a suggestion and its decision-log row is asserted against real Postgres
in `tests/integration/test_repository_real_postgres.py` -- that gap is exactly
how 4C.2's `4eafa80` defect reached CI, and TDD §16 makes the `real_infra` tier
mandatory for this engine because of it.

What this fake *does* reproduce faithfully, because these are decisions rather
than database behaviour:

* the conditional status transition (a second decide raises, it does not
  overwrite);
* keyset pagination on `(created_at DESC, id DESC)` with an opaque cursor and
  no offset;
* the append-only log -- there is no method here to update or delete one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    AutonomyLevelSetting,
    DecisionLogEntry,
    PermissionCategory,
    PermissionGrant,
    Policy,
    Suggestion,
    SuggestionStatus,
)
from nova_autonomy_engine.domain.ports import (
    SuggestionAlreadyDecidedError,
    SuggestionNotFoundError,
    SuggestionPage,
)
from nova_autonomy_engine.repository.cursor import decode_cursor, encode_cursor

__all__ = ["FakeAutonomyRepository"]


class FakeAutonomyRepository:
    def __init__(self) -> None:
        self.levels: dict[UUID, AutonomyLevelSetting] = {}
        self.policies: dict[UUID, Policy] = {}
        self.grants: dict[tuple[UUID, PermissionCategory], PermissionGrant] = {}
        self.suggestions: dict[UUID, Suggestion] = {}
        self.decision_log: list[DecisionLogEntry] = []
        self.healthy = True

    # --- Autonomy level -------------------------------------------------
    async def get_level(self, user_id: UUID) -> AutonomyLevelSetting | None:
        return self.levels.get(user_id)

    async def set_level(self, user_id: UUID, level: AutonomyLevel) -> AutonomyLevelSetting:
        setting = AutonomyLevelSetting(user_id=user_id, level=level, updated_at=datetime.now(UTC))
        self.levels[user_id] = setting
        return setting

    # --- Policies -------------------------------------------------------
    async def list_policies(self, user_id: UUID) -> list[Policy]:
        return sorted(
            (policy for policy in self.policies.values() if policy.user_id == user_id),
            key=lambda policy: (policy.created_at, str(policy.id)),
        )

    async def get_policy(self, user_id: UUID, policy_id: UUID) -> Policy | None:
        policy = self.policies.get(policy_id)
        return policy if policy is not None and policy.user_id == user_id else None

    async def create_policy(self, policy: Policy) -> Policy:
        self.policies[policy.id] = policy
        return policy

    async def replace_policy(self, policy: Policy) -> Policy | None:
        existing = self.policies.get(policy.id)
        if existing is None or existing.user_id != policy.user_id:
            return None
        updated = policy.model_copy(update={"updated_at": datetime.now(UTC)})
        self.policies[policy.id] = updated
        return updated

    async def delete_policy(self, user_id: UUID, policy_id: UUID) -> bool:
        policy = self.policies.get(policy_id)
        if policy is None or policy.user_id != user_id:
            return False
        del self.policies[policy_id]
        return True

    # --- Permission matrix ----------------------------------------------
    async def list_permission_grants(self, user_id: UUID) -> list[PermissionGrant]:
        return [grant for (owner, _), grant in self.grants.items() if owner == user_id]

    async def upsert_permission_grants(
        self, user_id: UUID, grants: list[PermissionGrant]
    ) -> list[PermissionGrant]:
        for grant in grants:
            self.grants[(user_id, grant.category)] = grant.model_copy(
                update={"user_id": user_id, "updated_at": datetime.now(UTC)}
            )
        return await self.list_permission_grants(user_id)

    # --- Suggestions ----------------------------------------------------
    async def insert_suggestion(
        self, suggestion: Suggestion, log_entry: DecisionLogEntry
    ) -> Suggestion:
        self.suggestions[suggestion.id] = suggestion
        self.decision_log.append(log_entry)
        return suggestion

    async def list_suggestions(
        self,
        user_id: UUID,
        *,
        status: SuggestionStatus | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> SuggestionPage:
        rows = [s for s in self.suggestions.values() if s.user_id == user_id]
        if status is not None:
            rows = [s for s in rows if s.status is status]
        rows.sort(key=lambda s: (s.created_at, s.id), reverse=True)
        if cursor is not None:
            after_created_at, after_id = decode_cursor(cursor)
            rows = [
                s
                for s in rows
                if (s.created_at, s.id) < (after_created_at, after_id)
            ]
        page = rows[:limit]
        has_more = len(rows) > limit
        next_cursor = (
            encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
        )
        return SuggestionPage(items=page, next_cursor=next_cursor)

    async def get_suggestion(self, user_id: UUID, suggestion_id: UUID) -> Suggestion | None:
        suggestion = self.suggestions.get(suggestion_id)
        return suggestion if suggestion is not None and suggestion.user_id == user_id else None

    async def decide_suggestion(
        self,
        user_id: UUID,
        suggestion_id: UUID,
        *,
        status: SuggestionStatus,
        log_entry: DecisionLogEntry,
    ) -> Suggestion:
        suggestion = self.suggestions.get(suggestion_id)
        if suggestion is None or suggestion.user_id != user_id:
            raise SuggestionNotFoundError(f"no suggestion {suggestion_id} for this user")
        if suggestion.status is not SuggestionStatus.PROPOSED:
            # The log still records the attempt -- the real repository does the
            # same, inside the transaction that rejects the transition.
            self.decision_log.append(log_entry)
            raise SuggestionAlreadyDecidedError(suggestion_id, suggestion.status)
        decided = suggestion.model_copy(
            update={"status": status, "decided_at": datetime.now(UTC)}
        )
        self.suggestions[suggestion_id] = decided
        self.decision_log.append(log_entry)
        return decided

    # --- Decision log (append-only: no update, no delete) ---------------
    async def append_decision_log(self, entry: DecisionLogEntry) -> DecisionLogEntry:
        self.decision_log.append(entry)
        return entry

    async def list_decision_log(
        self, *, subject_id: UUID | None = None, limit: int = 50
    ) -> list[DecisionLogEntry]:
        entries = self.decision_log
        if subject_id is not None:
            entries = [entry for entry in entries if entry.subject_id == subject_id]
        return sorted(entries, key=lambda e: (e.created_at, e.id), reverse=True)[:limit]

    async def count_suggestions(
        self, user_id: UUID, *, status: SuggestionStatus | None = None
    ) -> int:
        rows = [s for s in self.suggestions.values() if s.user_id == user_id]
        if status is not None:
            rows = [s for s in rows if s.status is status]
        return len(rows)

    async def ping(self) -> None:
        if not self.healthy:
            raise RuntimeError("fake repository marked unhealthy")

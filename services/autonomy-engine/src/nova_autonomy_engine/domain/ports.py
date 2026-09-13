"""Protocols this package depends on -- implements nothing itself.

`domain/` may only import this module, `nova_contracts`, and other `domain/`
modules -- never FastAPI, SQLAlchemy or `nova_eventbus_sdk`
(docs/architecture/03-backend-architecture.md §1), and per ADR-020 no
LLM/AI provider SDK. Every Protocol is defined here independently rather than
imported from another engine, following the per-consumer convention
`action-engine`, `reasoning-engine` and `executive-cognition-engine` each
already use for their own `domain/ports.py`.

**`AutonomyRepository` deliberately has no `update` or `delete` method for the
decision log.** TDD §9: *"`decision_log` is append-only."* The guarantee is
structural -- there is no method to call -- and
`tests/unit/test_repository_contract.py` asserts the absence by inspecting the
Protocol, the same way `agent-os/kernel` asserts its own append-only tables.
Bible Part 14: *"Store every important autonomous decision."*

**`ConversationalTrustSource` has no shipped non-degraded adapter in 4D**, and
that is a disclosed gap rather than an oversight -- see
`clients/conversational_trust.py` for the evidence. The Protocol is defined
here because the *semantics* of the read (a three-state answer, fail-closed on
two of them) are a 4D decision that TDD §5.3 and §13 bind, independently of
when a transport for it exists.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    AutonomyLevelSetting,
    DecisionLogEntry,
    PermissionGrant,
    Policy,
    Suggestion,
    SuggestionStatus,
    TrustInputStatus,
    TrustMetricSnapshot,
)

__all__ = [
    "FORBIDDEN_REPOSITORY_METHODS",
    "AutonomyRepository",
    "ConversationalTrustRead",
    "ConversationalTrustSource",
    "SuggestionAlreadyDecidedError",
    "SuggestionNotFoundError",
    "SuggestionPage",
]


class SuggestionNotFoundError(Exception):
    """No suggestion with that id for this user. TDD §13 maps it to a **404**,
    *"distinguished from a valid suggestion with no gates recorded"* -- which
    is why this is its own exception and not an empty result."""


class SuggestionAlreadyDecidedError(Exception):
    """The suggestion has already left `proposed`. TDD §13: *"Second decision
    is a **409**; the first stands."*

    Carries the standing status so the API can report which decision stands,
    rather than the caller having to re-read and race again.
    """

    def __init__(self, suggestion_id: UUID, status: SuggestionStatus) -> None:
        super().__init__(
            f"suggestion {suggestion_id} was already decided ({status.value}); "
            f"the first decision stands"
        )
        self.suggestion_id = suggestion_id
        self.status = status


class SuggestionPage(BaseModel):
    """One keyset page. `next_cursor` is **opaque** to every caller above the
    repository -- TDD §8.1/§9 forbid offset pagination anywhere, and an opaque
    cursor is what stops a client from reconstructing one."""

    items: list[Suggestion]
    next_cursor: str | None = None


class ConversationalTrustRead(BaseModel):
    """The result of consulting 2D-D's conversational trust signal.

    **Three states, not an `Optional`** (TDD §16 control 12): "the source is
    unreachable" and "the source has no metric for this user" both produce a
    `None` score, but reporting the first as the second would be reporting a
    degraded upstream as an empty success. `detail` carries the reason for a
    human reader of the panel and the decision log.
    """

    status: TrustInputStatus
    snapshot: TrustMetricSnapshot | None = None
    detail: str | None = None


@runtime_checkable
class ConversationalTrustSource(Protocol):
    """Reads `digital-twin-engine`'s 2D-D `TrustMetric` for one user.

    The return type is this engine's own `TrustMetricSnapshot`, never 2D-D's
    `TrustMetric` class: import-linter's "Engines are independent" contract
    forbids `nova_autonomy_engine` importing `nova_digital_twin_engine`, and
    the snapshot mirrors the shipped field shape rather than sharing the type.

    **An implementation must never raise.** A transport failure is reported as
    `status=UNAVAILABLE`, because a raising source would make the trust stage
    able to fail a decision that TDD §13 says must degrade to "insufficient
    evidence" instead.
    """

    async def read(self, user_id: UUID) -> ConversationalTrustRead: ...


@runtime_checkable
class AutonomyRepository(Protocol):
    """Persistence for the five `autonomy.*` tables (TDD §9).

    **One logical operation, one transaction, one commit** (decision D-3, as
    4C.2 applied it). `decide_suggestion` is the operation that makes this
    binding: the status change and its decision-log row are written in the
    **same transaction**, and the `real_infra` tier asserts the coupling
    against real Postgres because -- as 4C.2's `4eafa80` defect proved -- a
    fake repository cannot exercise a foreign key.
    """

    # --- Autonomy level -------------------------------------------------
    async def get_level(self, user_id: UUID) -> AutonomyLevelSetting | None:
        """`None` when the user has never set one. The caller applies the
        default (Level 0, Observation Only) rather than this method inventing a
        row, so "never configured" stays distinguishable from "set to 0"."""
        ...

    async def set_level(self, user_id: UUID, level: AutonomyLevel) -> AutonomyLevelSetting: ...

    # --- Policies -------------------------------------------------------
    async def list_policies(self, user_id: UUID) -> list[Policy]: ...

    async def get_policy(self, user_id: UUID, policy_id: UUID) -> Policy | None: ...

    async def create_policy(self, policy: Policy) -> Policy: ...

    async def replace_policy(self, policy: Policy) -> Policy | None:
        """Full replacement of an existing row; `None` when it does not exist.
        The API's `PATCH` reads, merges and replaces, so partial-update
        semantics live in one place above the repository instead of being
        re-derived per column here."""
        ...

    async def delete_policy(self, user_id: UUID, policy_id: UUID) -> bool: ...

    # --- Permission matrix ----------------------------------------------
    async def list_permission_grants(self, user_id: UUID) -> list[PermissionGrant]: ...

    async def upsert_permission_grants(
        self, user_id: UUID, grants: list[PermissionGrant]
    ) -> list[PermissionGrant]:
        """Upsert the supplied categories only. Categories not named are left
        as they were -- **not** reset to a permissive default, which would let a
        partial write widen authority."""
        ...

    # --- Suggestions ----------------------------------------------------
    async def insert_suggestion(
        self, suggestion: Suggestion, log_entry: DecisionLogEntry
    ) -> Suggestion:
        """Record a proposal and the decision that produced it **in one
        transaction**. The log entry's `subject_id` is the suggestion's id, so
        the child row's foreign key requires the parent INSERT to be ordered
        first -- the `4eafa80` trap TDD §9 requires designing out."""
        ...

    async def list_suggestions(
        self,
        user_id: UUID,
        *,
        status: SuggestionStatus | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> SuggestionPage:
        """Keyset paginated on `(created_at DESC, id DESC)`. **No offset
        parameter exists** -- TDD §8.1/§9."""
        ...

    async def get_suggestion(self, user_id: UUID, suggestion_id: UUID) -> Suggestion | None: ...

    async def decide_suggestion(
        self,
        user_id: UUID,
        suggestion_id: UUID,
        *,
        status: SuggestionStatus,
        log_entry: DecisionLogEntry,
    ) -> Suggestion:
        """Move a suggestion out of `proposed` and append its decision-log row
        **in the same transaction**.

        Raises `SuggestionNotFoundError` (-> 404) or
        `SuggestionAlreadyDecidedError` (-> 409). The status transition is
        conditional on the row still being `proposed` **in the database**, not
        on a prior read -- a check-then-write would let two concurrent
        approvals both succeed.
        """
        ...

    # --- Decision log (append-only: no update, no delete) ---------------
    async def append_decision_log(self, entry: DecisionLogEntry) -> DecisionLogEntry:
        """Append a decision that produced no suggestion -- a `deny` or an
        `observe_only`. Proposals and decisions go through
        `insert_suggestion`/`decide_suggestion` so the coupling stays in one
        transaction."""
        ...

    async def list_decision_log(
        self, *, subject_id: UUID | None = None, limit: int = 50
    ) -> list[DecisionLogEntry]: ...

    async def count_suggestions(
        self, user_id: UUID, *, status: SuggestionStatus | None = None
    ) -> int:
        """Counts for the overview widget. A count, not a page -- the panel's
        first paint needs the number without fetching the rows."""
        ...

    async def ping(self) -> None:
        """Readiness probe. Raises on an unusable connection so
        `/internal/readiness` reports **not ready** instead of a healthy-looking
        503-less success (TDD §16 control 12)."""
        ...


FORBIDDEN_REPOSITORY_METHODS: frozenset[str] = frozenset(
    {
        "update_decision_log",
        "delete_decision_log",
        "truncate_decision_log",
        "clear_decision_log",
    }
)
"""Names `AutonomyRepository` and every implementation of it must never grow.

Declared as data, not prose, so `tests/unit/test_repository_contract.py` can
assert their absence mechanically -- from the Protocol, the fake and the
Postgres repository alike -- rather than the append-only guarantee resting on
review. TDD §9; the same shape `agent-os/kernel` uses for its own append-only
tables."""

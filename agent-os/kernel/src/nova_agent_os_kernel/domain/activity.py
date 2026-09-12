"""Agent activity -- the append-only record of what an agent instance did.

Phase 4C milestone 4C.2b (approved 2026-09-08). Persistence and domain
foundation only: nothing writes an activity row yet. The write call sites
(`domain/scheduler.py`, `domain/reconciliation.py`, the peer-review path)
belong to 4C.2d, and the read endpoint to 4C.2c.

**Why the Kernel owns this.** Every transition an activity row records is one
the Kernel already performs on its own `agent_instance` table. Keeping both in
one component -- and, per `action-engine`'s own `ActionRepository` precedent
(four tables, one port), in one repository -- is what lets a status change and
its activity row commit in a single transaction without inventing a second
transaction abstraction to coordinate two repositories.

**Append-only, and enforced rather than described.** The repository exposes
`append_activity` and `list_activity` and no update or delete of any kind;
`tests/unit/test_activity.py` asserts that surface, so a mutation method
cannot be added quietly. History that can be rewritten is not history.

**`occurred_at` is stamped in Python, never by the database.** `new_activity()`
is the one place time enters, so it is greppable and testable. This is not
stylistic: Postgres `now()` is *transaction-start* time and is constant for
every statement in a transaction, so a `server_default` would give every row
written in one transaction an identical timestamp -- which is exactly the tie
the cursor below has to break. Phase 4B hit this on `task_graph.created_at`
and had to stamp explicitly to test ordering at all.

**Ordering is `(occurred_at DESC, id DESC)`, and the cursor uses the same
composite key.** Ties on `occurred_at` are expected rather than hypothetical
(see above), so a cursor keyed on the timestamp alone would skip or repeat
rows at a tie boundary. `id` makes the order total. Keyset, never offset: an
offset walks rows the database has already discarded and shifts under
concurrent inserts, and this table only ever grows.
"""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

__all__ = [
    "ActivityCursor",
    "ActivityPage",
    "AgentActivity",
    "AgentActivityKind",
    "InvalidCursorError",
    "decode_cursor",
    "encode_cursor",
    "new_activity",
]


class AgentActivityKind(StrEnum):
    """The closed set of activities the Kernel records.

    Closed deliberately. Every member corresponds to a transition that already
    exists in `domain/scheduler.py` or `domain/reconciliation.py` today -- none
    was invented to give the panel something to show, and none may be added
    without a code path that genuinely produces it:

    * `DISPATCHED`      -- an `agent_instance` row was written `"running"`
                           before `spawn()` (`_spawn_tracked`).
    * `COMPLETED`       -- that instance reached its terminal `"completed"`.
    * `FAILED`          -- it reached its terminal `"failed"`.
    * `RESTART_PLANNED` -- the owning Supervisor returned this instance in its
                           restart plan (`dispatch_task_node`).
    * `INTERRUPTED`     -- Kernel restart reconciliation found the row still
                           `"running"` and its process gone
                           (`reconcile_running_instances`).
    * `PEER_REVIEW`     -- a peer-review round returned a verdict
                           (`_finalize_outcome`).
    """

    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTART_PLANNED = "restart_planned"
    INTERRUPTED = "interrupted"
    PEER_REVIEW = "peer_review"


class AgentActivity(BaseModel):
    """One immutable fact about one agent instance.

    No `updated_at` and no soft-delete flag: a row is written once and never
    changes, so a column recording when it last changed would always be a lie.

    `detail` carries the per-kind structure (a completed instance's outcome, a
    peer-review round's `reviewer_category`/`peer_validation`). It is
    deliberately untyped here -- 4C.2b persists activity; 4C.2d is what decides
    what each kind puts in it, and fixing a shape now would be guessing on
    behalf of a slice that has not been designed.
    """

    id: UUID
    agent_instance_id: UUID
    """FK to `agent_os.agent_instance.id`. Unlike `agent_instance`'s own
    `agent_package_id` -- which points across a component boundary at
    Registry's table and therefore carries no constraint -- this points at a
    table the same component owns and migrates, so the constraint is real."""
    occurred_at: datetime
    kind: AgentActivityKind
    correlation_id: UUID | None = None
    """First-class provenance: the correlation id that ties this activity back
    through `agent_os.task.completed`, `planning.task_graph.created` and the
    reasoning process that started the chain.

    **Typed and first-class rather than a key inside `detail`.** It is the one
    field here that is a join key rather than description -- what makes
    "reasoning -> plan -> instance -> activity -> peer review" a traversable
    chain instead of a story. Burying it in JSON would keep it readable and
    make it unqueryable, and would leave its type unenforced.

    **Nullable, and never fabricated.** `None` means "no correlation is known
    for this activity", which is a true statement; minting a fresh UUID to
    avoid a null would manufacture provenance that links nothing, and a reader
    could not tell the difference. Every caller that has one passes it; a
    caller that does not passes nothing.

    **Not part of the ordering key.** `(occurred_at DESC, id DESC)` is the
    total order and the cursor, unchanged by this field. Two activities with
    different correlation ids interleave strictly by time, and the cursor
    never encodes a correlation id -- asserted in `tests/unit/test_activity.py`
    and again against real Postgres."""
    detail: dict = Field(default_factory=dict)


def new_activity(
    *,
    agent_instance_id: UUID,
    kind: AgentActivityKind,
    correlation_id: UUID | None = None,
    detail: dict | None = None,
) -> AgentActivity:
    """Mint an activity stamped with the current UTC time.

    The single place `datetime.now(UTC)` is called for this table. A caller
    that needs a specific time (a test asserting ordering, a backfill that
    never happens) constructs `AgentActivity` directly and says so.

    `correlation_id` defaults to `None` and is **never generated here**. Every
    call site in 4C.2d already holds the correlation id of the work it is
    recording -- the Scheduler threads one through every dispatch -- so a
    default that minted one would only ever be reached by a caller that had
    lost it, and would hide that loss behind a valid-looking id.
    """
    return AgentActivity(
        id=uuid4(),
        agent_instance_id=agent_instance_id,
        occurred_at=datetime.now(UTC),
        kind=kind,
        correlation_id=correlation_id,
        detail=detail if detail is not None else {},
    )


class InvalidCursorError(ValueError):
    """A cursor that did not come from `encode_cursor`, or was corrupted.

    Raised rather than silently ignored: a caller whose cursor is rejected has
    asked for a specific page, and quietly restarting at page one would give
    them rows they already saw while looking like success.
    """


#: `(occurred_at, id)` -- the composite ordering key, in ordering order.
ActivityCursor = tuple[datetime, UUID]


_SEPARATOR = "|"


def encode_cursor(occurred_at: datetime, activity_id: UUID) -> str:
    """Encode the ordering key as an opaque, URL-safe string.

    Opaque so callers cannot construct one by hand and depend on its shape;
    URL-safe because 4C.2c carries it in a query parameter. Padding is stripped
    so the value never needs escaping.

    Deterministic: the same key always encodes to the same string. That is
    asserted, not assumed -- a cursor that varied per call would make paging
    irreproducible and every ordering test flaky.
    """
    raw = f"{occurred_at.isoformat()}{_SEPARATOR}{activity_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> ActivityCursor:
    """Reverse `encode_cursor`, validating every part.

    Rejects anything that is not base64, not UTF-8, missing the separator,
    not a parseable timestamp, not a parseable UUID, or timezone-naive. A
    naive timestamp cannot come from `encode_cursor` (which encodes an aware
    one) and comparing it against a `TIMESTAMPTZ` column would raise deep
    inside the driver, so it is refused here where the error can say why.

    The returned timestamp is normalised to UTC, so two cursors naming the
    same instant in different offsets page identically.
    """
    if not cursor:
        raise InvalidCursorError("cursor is empty")

    padding = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(cursor + padding).decode()
    except (binascii.Error, ValueError) as exc:
        raise InvalidCursorError(f"cursor is not valid base64: {cursor!r}") from exc

    timestamp_part, separator, id_part = raw.rpartition(_SEPARATOR)
    if not separator:
        raise InvalidCursorError(f"cursor is missing its {_SEPARATOR!r} separator")

    try:
        occurred_at = datetime.fromisoformat(timestamp_part)
    except ValueError as exc:
        raise InvalidCursorError(
            f"cursor timestamp is not an ISO-8601 datetime: {timestamp_part!r}"
        ) from exc
    if occurred_at.tzinfo is None:
        raise InvalidCursorError("cursor timestamp has no timezone")

    try:
        activity_id = UUID(id_part)
    except ValueError as exc:
        raise InvalidCursorError(f"cursor id is not a UUID: {id_part!r}") from exc

    return occurred_at.astimezone(UTC), activity_id


class ActivityPage(BaseModel):
    """One page, plus the cursor that continues it.

    `next_cursor is None` means this page is the last one. It is never a
    cursor pointing at nothing: the repository asks for one row beyond the
    page and only emits a cursor when that row exists, so a caller never
    follows a cursor to an empty page it could have avoided.
    """

    items: list[AgentActivity] = Field(default_factory=list)
    next_cursor: str | None = None

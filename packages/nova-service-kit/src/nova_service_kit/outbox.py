"""The transactional outbox dispatch loop -- identical `dispatch_ready_events`
logic across every engine that publishes via a Postgres outbox table (Project
Health Review, August 2026; `docs/design/nova-service-kit/
boilerplate-extraction-proposal.md` Extraction C). Parameterized entirely over
structural `Protocol`s (never a concrete engine's own repository, row, or
metrics type), so this module never imports any engine's own top-level
package (ADR-034) -- an engine's own `OutboxRow`/`<Engine>Repository`/
`<Engine>Metrics` classes satisfy these protocols structurally, with no
inheritance and no import in either direction.

Deliberately excludes the two-phase saga step (`apply_pending_graph_writes`)
`knowledge-engine`/`world-model-engine` each have -- that step is genuinely
engine-specific (touches `nova_graphstore_sdk` and each engine's own
`object_graph`/domain logic), not boilerplate, and stays in each of those two
engines' own `repository/outbox_dispatcher.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from nova_contracts import EventEnvelope

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from nova_eventbus_sdk import EventBus

DEFAULT_BATCH_SIZE = 100


class OutboxRow(Protocol):
    """Read-only structural shape -- declared as properties, not plain
    attributes, so an engine's own Pydantic `OutboxRow` (whose `payload` is
    concretely `dict[str, Any]`, a subtype of this Protocol's `Mapping[str,
    Any]`) satisfies this Protocol covariantly. A plain-attribute Protocol
    member requires mypy to check invariant (get *and* set) compatibility,
    which `dict[str, Any]` fails against `Mapping[str, Any]` even though
    every concrete engine's row is always read-only here."""

    @property
    def id(self) -> UUID: ...
    @property
    def subject(self) -> str: ...
    @property
    def payload(self) -> Mapping[str, Any]: ...
    @property
    def correlation_id(self) -> UUID: ...
    @property
    def causation_id(self) -> UUID | None: ...


class OutboxRepository(Protocol):
    async def list_dispatch_ready(
        self, *, limit: int = DEFAULT_BATCH_SIZE
    ) -> Sequence[OutboxRow]: ...

    async def mark_dispatched(self, outbox_id: UUID) -> None: ...


class _Counter(Protocol):
    def add(self, amount: int, attributes: Mapping[str, str] | None = None) -> None: ...


class OutboxMetrics(Protocol):
    """`outbox_dispatched_total` is a read-only property for the same reason
    as `OutboxRow`'s fields above -- covariant matching against every
    engine's own concrete `opentelemetry.metrics.Counter`-typed attribute,
    without this package taking on an `opentelemetry` dependency it doesn't
    otherwise need (out of scope per this package's own README)."""

    @property
    def outbox_dispatched_total(self) -> _Counter: ...


async def dispatch_ready_events(
    repository: OutboxRepository,
    bus: EventBus,
    *,
    source_engine: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    metrics: OutboxMetrics | None = None,
) -> int:
    """Publish every dispatch-ready outbox row, oldest first; mark each
    dispatched right after its own publish succeeds. Returns the number of
    rows dispatched.

    The outbox row's own `id` is reused as `EventEnvelope.event_id` so a
    retried publish after a crash carries the same `event_id`, enabling
    exactly-once delivery via consumer-side `event_id` dedup -- the
    convention every engine's outbox dispatcher already used before this
    extraction.
    """
    dispatched = 0
    rows = await repository.list_dispatch_ready(limit=batch_size)
    for row in rows:
        envelope = EventEnvelope(
            event_id=row.id,
            subject=row.subject,
            source_engine=source_engine,
            correlation_id=row.correlation_id,
            causation_id=row.causation_id,
            payload=row.payload,
        )
        await bus.publish(envelope)
        await repository.mark_dispatched(row.id)
        dispatched += 1
        if metrics is not None:
            metrics.outbox_dispatched_total.add(1, {"subject": row.subject})
    return dispatched

"""Persists historically-dated memories so the browser has an AC-6 gap to see.

**Why this exists, stated plainly rather than hidden.** AC-6 requires that *"the
Digital Twin's project model correctly reconstructs 'what was I doing on Project
X' after a simulated multi-week gap, and the reconstruction is visible in the
Digital Twin panel"*. The browser's half -- opening the panel, choosing the
project, and reading a reconstruction whose gap is genuinely weeks wide -- is
what the Digital Twin panel does, through `api-gateway` like everything else.

*Producing* weeks-old memories is the half no shipped component performs, and
cannot: a memory is created when it is created. Nothing in this repository
defines a clock-injection facility, a time-travel fixture, or any convention for
simulated elapsed time, and ratified decision **TDD 4E §20.1** settled that the
gap is simulated **in the data, not in the clock**. So this script stands in for
the months of ordinary use a real installation would have accumulated.

**It stands in for elapsed time, not for the engine.** Every record goes through
the **real** `PostgresMemoryRepository.create_long_term` against **real**
PostgreSQL, with the real transactional outbox row written in the same
transaction -- so `memory-engine`'s own outbox worker publishes real
`memory.long_term.created` events over the real Event Bus, and
`digital-twin-engine`'s real subscriber derives from them. Nothing here writes
SQL of its own, nothing bypasses the repository, and nothing touches
`digital-twin-engine` directly: the driver's only contact with the Digital Twin
is the same event stream a production write would produce.

**Why it builds `MemoryRecord` itself rather than calling `long_term.write()`.**
`write()` takes no `created_at` -- deliberately, and §20.1 forbids widening it,
`CreateMemoryRequest`, or any Memory HTTP contract to make this test easier. So
the record is constructed with the timestamp it should have and handed to the
same repository method `write()` hands it to, with the same outbox payload
`write()` builds. The seam is one function call earlier than production's; the
persistence path is identical.

**What it does not prove**, so the Gate Review can say so without hedging: that
NOVA accumulates months of memory on its own initiative. It does not, in a
fresh E2E stack -- there is no user and no history. Everything downstream of the
write is real: the outbox, the bus, the subscriber, the derivation, the
timestamps in `digital_twin.domain_evidence`, the gap arithmetic, and the panel.

Usage:

    uv run python tools/e2e_seed_digital_twin_project.py

Prints the seeded `project_id` on stdout so the caller can hand it to
Playwright. Exits non-zero, with the reason on stderr, if the rows did not
persist with the timestamps they were given -- which is the one failure worth
stopping for, since a gap that silently collapsed to zero would leave the AC-6
spec asserting nothing.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from nova_contracts import LongTermMemoryCreatedPayload
from nova_memory_engine.config import Settings
from nova_memory_engine.domain.models import MemoryRecord, MemoryType, PrivacyLevel
from nova_memory_engine.domain.ports import OutboxEvent
from nova_memory_engine.repository.postgres_memory_repository import PostgresMemoryRepository
from nova_service_kit import create_engine, create_session_factory

_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
"""ADR-025's single trusted user, matching `digital-twin-engine`'s own
`primary_user_id` default -- the identity the panel will read as."""

#: What was being worked on, and when. The oldest is ~4 months back and the
#: newest ~5 weeks, so the reconstruction has both a real activity *window* to
#: report and a real multi-week gap since. Content is ordinary project prose:
#: nothing here is private, and nothing is surfaced by the Digital Twin anyway
#: (no subscribed payload carries memory content -- TDD 4E §5.2).
_HISTORY: tuple[tuple[int, MemoryType, str], ...] = (
    (118, MemoryType.PROJECT, "Chose the transactional outbox over dual writes."),
    (96, MemoryType.EPISODIC, "Paired on the ingest retry loop; settled on jittered backoff."),
    (74, MemoryType.PROCEDURAL, "Release runbook: migrate, roll workers, then the API."),
    (52, MemoryType.DECISION, "Kept keyset pagination rather than offsets for the inbox."),
    (37, MemoryType.PROJECT, "Left the schema migration half-written on the branch."),
)

_MIN_EXPECTED_GAP_DAYS = 21
"""What "multi-week" means for the check below. The newest record is 37 days
back, so this has ample margin -- it exists to catch a *collapsed* gap (every
row landing at `now`), not to police the exact ages above."""


def _record(age_days: int, memory_type: MemoryType, content: str, project_id: UUID) -> MemoryRecord:
    created_at = datetime.now(UTC) - timedelta(days=age_days)
    return MemoryRecord(
        memory_type=memory_type,
        content=content,
        user_id=_USER_ID,
        project_id=project_id,
        # INTERNAL, so these contribute: the Digital Twin's allow-list is
        # PUBLIC/INTERNAL only (TDD 4E §0.1.6). The PRIVATE-exclusion negative
        # control seeds its own CONFIDENTIAL record separately -- see below.
        privacy_level=PrivacyLevel.INTERNAL,
        importance_score=0.6,
        created_at=created_at,
        # An insert was never an update. Passing both keeps the round trip
        # lossless and matches what `update()` already does with `updated_at`.
        updated_at=created_at,
    )


def _outbox_event(record: MemoryRecord) -> OutboxEvent:
    """The same payload `long_term.write()` builds, field for field.

    Duplicated rather than imported because `write()` cannot be given a
    `created_at` (§20.1), and a driver that quietly published a *different*
    payload shape than production would be testing its own invention.
    """
    return OutboxEvent(
        subject="memory.long_term.created",
        payload=LongTermMemoryCreatedPayload(
            memory_id=record.id,
            user_id=record.user_id,
            project_id=record.project_id,
            memory_type=record.memory_type,
            importance_score=record.importance_score,
            confidence=record.confidence,
            privacy_level=record.privacy_level,
            knowledge_node_id=record.knowledge_node_id,
            created_at=record.created_at,
        ).model_dump(mode="json"),
        correlation_id=uuid4(),
    )


async def _main() -> int:
    settings = Settings()
    engine = create_engine(settings.postgres_dsn)
    repository = PostgresMemoryRepository(create_session_factory(engine))
    project_id = uuid4()

    try:
        persisted: list[MemoryRecord] = []
        for age_days, memory_type, content in _HISTORY:
            record = _record(age_days, memory_type, content, project_id)
            persisted.append(
                await repository.create_long_term(record, outbox_event=_outbox_event(record))
            )

        # A CONFIDENTIAL memory on the same project, for the negative control
        # (TDD 4E §14.5 control 6, ratified §19.3). It is written through the
        # identical real path; the Digital Twin must record no evidence for it,
        # so the project's memory_count must stay at len(_HISTORY).
        private = _record(20, MemoryType.PROJECT, "Rotated the staging credentials.", project_id)
        private = private.model_copy(update={"privacy_level": PrivacyLevel.CONFIDENTIAL})
        await repository.create_long_term(private, outbox_event=_outbox_event(private))

        # Assert the one thing whose failure would make the AC-6 spec vacuous:
        # that the timestamps survived. Before the §20.1 fix `create_long_term`
        # omitted `created_at` entirely and the column default silently replaced
        # every value here with `now()` -- the gap would have been zero and the
        # spec would still have "passed" against a reconstruction of nothing.
        oldest = min(r.created_at for r in persisted)
        newest = max(r.created_at for r in persisted)
        gap_days = (datetime.now(UTC) - newest).total_seconds() / 86400.0
        if gap_days < _MIN_EXPECTED_GAP_DAYS:
            print(
                f"seeded rows are only {gap_days:.1f} days old; expected at least "
                f"{_MIN_EXPECTED_GAP_DAYS}. The historical created_at values did not "
                f"persist -- check PostgresMemoryRepository.create_long_term.",
                file=sys.stderr,
            )
            return 1

        print(
            f"seeded {len(persisted)} memories for project {project_id}: "
            f"{oldest.date()} to {newest.date()}, {gap_days:.0f}-day gap "
            f"(+1 confidential record that must not appear)",
            file=sys.stderr,
        )
        print(project_id)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    os.environ.setdefault(
        "MEMORY_ENGINE_POSTGRES_DSN",
        "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova",
    )
    raise SystemExit(asyncio.run(_main()))

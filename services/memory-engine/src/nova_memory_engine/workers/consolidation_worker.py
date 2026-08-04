"""Consolidation worker -- Arq scheduled job driving `domain/consolidation.py` and
`domain/lifecycle.py` against `MemoryRepository` (docs/design/phase-1/
01-memory-engine.md §6). Scheduled every `Settings.consolidation_interval_hours`
(a fixed interval for Phase 1; Phase 4's Cognitive State Engine will eventually pick
idle time instead of a clock).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from nova_observability import get_logger

from nova_memory_engine.domain import consolidation, long_term
from nova_memory_engine.domain.models import LifecycleState
from nova_memory_engine.domain.ports import MemoryRepository

if TYPE_CHECKING:
    from nova_memory_engine.observability import MemoryEngineMetrics

logger = get_logger("memory-engine.workers.consolidation")

CANDIDATE_LOOKBACK = timedelta(days=180)
"""How far back `list_candidates_for_consolidation` looks each run -- generous
enough to catch memories that only recently crossed a passive lifecycle threshold,
without an unbounded full-table scan every run (docs/design/phase-1/
01-memory-engine.md §15's <5min-at-10K-candidates target assumes a bounded scan)."""

WORKER_ACTOR = "consolidation_worker"


def _days_since(moment: datetime, now: datetime) -> float:
    return max((now - moment).total_seconds() / 86400.0, 0.0)


async def run_consolidation(
    repository: MemoryRepository,
    *,
    now: datetime | None = None,
    metrics: MemoryEngineMetrics | None = None,
) -> None:
    """The full run (docs/design/phase-1/01-memory-engine.md §6 steps 1-6):

    1. Record a `consolidation_run` row.
    2. Fetch candidates, plan merges and passive lifecycle advances (pure, in
       `domain/consolidation.py`).
    3. Execute merges: supersede duplicates via the `DUPLICATE_MERGED` explicit
       trigger (never a hard delete -- see `domain/lifecycle.py`).
    4. Execute lifecycle advances.
    5. Separately, check every `scheduled_for_deletion` record's grace period and
       hard-delete the ones that elapsed it -- this is the only path to `DELETED`
       (docs/design/phase-1/01-memory-engine.md §6).
    6. Mark the run completed with counts, or failed if an exception escapes.
    """
    now = now or datetime.now(UTC)
    run_id = await repository.start_consolidation_run()
    logger.info("consolidation run started", extra={"run_id": str(run_id)})

    try:
        records = await repository.list_candidates_for_consolidation(
            since=now - CANDIDATE_LOOKBACK
        )
        by_id = {r.id: r for r in records}
        candidates = [
            consolidation.ConsolidationCandidate(
                memory_id=r.id,
                user_id=r.user_id,
                project_id=r.project_id,
                embedding=r.embedding,
                confidence=r.confidence,
                importance_score=r.importance_score,
                lifecycle_state=r.lifecycle_state,
                days_since_last_access=_days_since(r.last_accessed_at or r.created_at, now),
                has_active_project_reference=r.project_id is not None,
            )
            for r in records
        ]
        plan = consolidation.plan_consolidation(candidates)

        records_merged = 0
        for merge in plan.merges:
            for superseded_id in merge.superseded_ids:
                owner = by_id[superseded_id].user_id
                await long_term.transition_lifecycle(
                    repository,
                    superseded_id,
                    user_id=owner,
                    next_state=LifecycleState.SCHEDULED_FOR_DELETION,
                    reason=f"duplicate of {merge.keep_id} (cosine similarity > "
                    f"{consolidation.DUPLICATE_SIMILARITY_THRESHOLD})",
                    action="duplicate_merged",
                    actor=WORKER_ACTOR,
                    correlation_id=uuid4(),
                )
                records_merged += 1

        for advance in plan.lifecycle_advances:
            owner = by_id[advance.memory_id].user_id
            await long_term.transition_lifecycle(
                repository,
                advance.memory_id,
                user_id=owner,
                next_state=advance.to_state,
                reason=advance.reason,
                action="lifecycle_advanced",
                actor=WORKER_ACTOR,
                correlation_id=uuid4(),
            )

        records_deleted = await _hard_delete_elapsed(repository, now=now)

        await repository.complete_consolidation_run(
            run_id,
            records_scanned=len(records),
            records_merged=records_merged,
            records_advanced=len(plan.lifecycle_advances),
            records_deleted=records_deleted,
            status="completed",
        )
        if metrics is not None:
            metrics.consolidation_records_total.add(records_merged, {"outcome": "merged"})
            metrics.consolidation_records_total.add(
                len(plan.lifecycle_advances), {"outcome": "advanced"}
            )
            metrics.consolidation_records_total.add(records_deleted, {"outcome": "deleted"})
        logger.info(
            "consolidation run completed",
            extra={
                "run_id": str(run_id),
                "records_scanned": len(records),
                "records_merged": records_merged,
                "records_advanced": len(plan.lifecycle_advances),
                "records_deleted": records_deleted,
            },
        )
    except Exception:
        # `complete_consolidation_run` still runs so the row doesn't stay
        # `status='running'` forever -- docs/design/phase-1/01-memory-engine.md §17's
        # crash-recovery detection is for a *process* dying mid-run (no chance to
        # reach this handler); an in-process exception is handled directly, here.
        logger.exception("consolidation run failed", extra={"run_id": str(run_id)})
        await repository.complete_consolidation_run(
            run_id,
            records_scanned=0,
            records_merged=0,
            records_advanced=0,
            records_deleted=0,
            status="failed",
        )
        raise


async def _hard_delete_elapsed(repository: MemoryRepository, *, now: datetime) -> int:
    from nova_memory_engine.domain import lifecycle

    scheduled = await repository.list_scheduled_for_deletion()
    deleted = 0
    for record in scheduled:
        days_since_scheduled = _days_since(record.updated_at, now)
        next_state = lifecycle.next_state_on_grace_period_check(
            record.lifecycle_state, days_since_scheduled=days_since_scheduled
        )
        if next_state == LifecycleState.DELETED:
            await long_term.transition_lifecycle(
                repository,
                record.id,
                user_id=record.user_id,
                next_state=next_state,
                reason=f"grace period ({days_since_scheduled:.1f}d) elapsed",
                action="deleted",
                actor=WORKER_ACTOR,
                correlation_id=uuid4(),
            )
            deleted += 1
    return deleted


async def arq_run_consolidation(ctx: dict) -> None:  # noqa: ARG001 -- Arq's job signature
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_consolidation(ctx["memory_repository"], metrics=ctx.get("metrics"))


async def run_short_term_expiry(
    repository: MemoryRepository, *, now: datetime | None = None
) -> int:
    """Short Term Memory expiry -- docs/design/phase-1/01-memory-engine.md §4:
    "Expiry is enforced by workers/consolidation_worker.py, not a Postgres-native
    TTL." Deliberately a separate, more frequent job from `run_consolidation`
    rather than bundled into it: short-term memories have an hours-to-days TTL, far
    tighter than consolidation's 6-hour default cycle (`Settings.
    short_term_expiry_check_interval_minutes`, 15 minutes by default)."""
    from nova_memory_engine.domain import short_term

    deleted = await short_term.expire_due(repository, now=now)
    if deleted:
        logger.info("short-term memory expiry", extra={"records_deleted": deleted})
    return deleted


async def arq_run_short_term_expiry(ctx: dict) -> None:  # noqa: ARG001 -- Arq's job signature
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_short_term_expiry(ctx["memory_repository"])

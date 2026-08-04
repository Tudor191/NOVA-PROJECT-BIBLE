"""Snapshot worker -- Arq scheduled job driving periodic World State Snapshots
(docs/design/phase-1/03-world-model-engine.md §2, §12). Manual/triggered
snapshots go through `api/snapshots.py`'s `POST /v1/world/snapshot` instead --
this worker only handles the `scheduled` trigger.

Phase 1 has no user-directory / active-user-discovery mechanism (a concern
that arguably belongs to Identity/Auth, not World Model) -- `run_scheduled_
snapshots` takes an explicit `user_ids` list rather than inventing a way to
discover it. `workers/__init__.py` currently has no real feed for this list,
so the scheduled cron entry point runs as a documented no-op until one exists
(see README's Known Limitations), rather than guessing at a user source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from nova_observability import get_logger

from nova_world_model_engine.domain.models import Snapshot
from nova_world_model_engine.domain.ports import ContextRepository, WorldHistoryRepository

if TYPE_CHECKING:
    from nova_world_model_engine.observability import WorldModelEngineMetrics

logger = get_logger("world-model-engine.workers.snapshot")


async def run_scheduled_snapshots(
    context_repo: ContextRepository,
    history_repo: WorldHistoryRepository,
    *,
    user_ids: list[UUID],
    metrics: WorldModelEngineMetrics | None = None,
) -> int:
    taken = 0
    for user_id in user_ids:
        context = await context_repo.get_context(user_id)
        snapshot_data = context.model_dump(mode="json") if context is not None else {}
        snapshot = Snapshot(user_id=user_id, snapshot_data=snapshot_data, trigger="scheduled")
        await history_repo.create_snapshot(snapshot)
        taken += 1
        if metrics is not None:
            metrics.snapshots_taken_total.add(1, {"trigger": "scheduled"})
    if taken:
        logger.info("scheduled snapshots taken", extra={"count": taken})
    return taken


async def arq_run_scheduled_snapshots(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_scheduled_snapshots(
        ctx["context_repository"],
        ctx["history_repository"],
        user_ids=ctx.get("known_user_ids", []),
        metrics=ctx.get("metrics"),
    )

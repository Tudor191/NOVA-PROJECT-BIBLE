"""Active Context management -- docs/design/phase-1/03-world-model-engine.md
§4/§7. Owns Active Context (current objective/project/device/task); must never
persist it primarily to Postgres -- Redis (`ContextRepository`) is the store
(§1's component table).

Every update here enqueues at most one `world_model.context.changed` outbox row,
riding along in whichever Postgres write the caller is already making (e.g.
`fusion.py`'s history append) -- Active Context updates carry no `graph_write`
intent of their own (Redis state is never graph-backed), so the outbox row here
is always dispatch-ready immediately (§17 draws this distinction explicitly).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from nova_contracts import ContextChangedPayload

from nova_world_model_engine.domain.models import ActiveContext
from nova_world_model_engine.domain.ports import (
    ContextRepository,
    OutboxEvent,
    WorldHistoryRepository,
)

_UPDATABLE_FIELDS = ("objective", "project_id", "device", "task", "activity", "platform")


async def get_context(context_repo: ContextRepository, user_id: UUID) -> ActiveContext | None:
    return await context_repo.get_context(user_id)


async def update_context(
    context_repo: ContextRepository,
    history_repo: WorldHistoryRepository,
    *,
    user_id: UUID,
    updates: dict[str, Any],
    confidence: float,
    correlation_id: UUID,
) -> ActiveContext:
    existing = await context_repo.get_context(user_id)
    merged: dict[str, Any] = {
        field: existing.__getattribute__(field) if existing is not None else None
        for field in _UPDATABLE_FIELDS
    }
    # A `None` in `updates` means "this caller has no opinion on this field",
    # not "clear it" -- a fused batch whose winning signal carries no `task`,
    # say, must not wipe out a `task` a previous update established. Explicit
    # clearing isn't a Phase 1 requirement (no caller needs it yet).
    merged.update(
        {k: v for k, v in updates.items() if k in _UPDATABLE_FIELDS and v is not None}
    )
    updated = ActiveContext(
        user_id=user_id, confidence=confidence, updated_at=datetime.now(UTC), **merged
    )
    await context_repo.put_context(updated)

    outbox = OutboxEvent(
        subject="world_model.context.changed",
        payload=ContextChangedPayload(
            user_id=user_id,
            objective=updated.objective,
            project_id=updated.project_id,
            device=updated.device,
            task=updated.task,
            activity=updated.activity,
            confidence=confidence,
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    await history_repo.enqueue_outbox(outbox)
    return updated


def scoped_view(context: ActiveContext, *, scope: str | None) -> dict[str, Any]:
    """Agent-scoped context filtering (Part 11 "Agent Awareness", §7 step 4) --
    filtering happens here, server-side, not by maintaining N pre-filtered
    copies. `scope=None` returns the full context. An agent category never
    receives the full Active Context and trusts itself to ignore irrelevant
    fields (§18); it receives only what it's scoped to."""
    full = context.model_dump(mode="json")
    if scope is None:
        return full
    category = scope.removeprefix("agent:")
    fields = _AGENT_SCOPE_FIELDS.get(category, _UPDATABLE_FIELDS)
    always_included = ("user_id", "confidence", "updated_at")
    return {k: full[k] for k in (*always_included, *fields) if k in full}


_AGENT_SCOPE_FIELDS: dict[str, tuple[str, ...]] = {
    "coding-agent": ("project_id", "task", "device"),
    "communication-engine": ("activity", "device", "platform"),
}
"""Per-category field whitelists (§7 step 4's worked examples: "a `coding-agent`
gets project/file/IDE fields; a `communication-engine` request gets
conversation/device fields"). Unlisted categories fall back to every updatable
field -- a documented default, not a silent full-context leak, since Active
Context itself never carries more than `_UPDATABLE_FIELDS` plus `confidence`/
`updated_at` (both always included)."""

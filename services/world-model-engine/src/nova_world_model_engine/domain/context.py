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

from nova_contracts import ContextChangedPayload, PresentIdentityPayload

from nova_world_model_engine.domain.models import ActiveContext, PresentIdentitySignal
from nova_world_model_engine.domain.ports import (
    ContextRepository,
    OutboxEvent,
    WorldHistoryRepository,
)

_UPDATABLE_FIELDS = ("objective", "project_id", "device", "task", "activity", "platform")


def _present_identities_payload(context: ActiveContext) -> list[PresentIdentityPayload]:
    return [
        PresentIdentityPayload(
            identity_id=signal.identity_id,
            confidence=signal.confidence,
            modality_summary=signal.modality_summary,
        )
        for signal in context.present_identities
    ]


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
            present_identities=_present_identities_payload(updated),
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    await history_repo.enqueue_outbox(outbox)
    return updated


async def upsert_present_identity(
    context_repo: ContextRepository,
    history_repo: WorldHistoryRepository,
    *,
    user_id: UUID,
    identity: PresentIdentitySignal,
    correlation_id: UUID,
) -> ActiveContext:
    """`perception.identity.observed` -> `ActiveContext.present_identities`
    (docs/design/phase-2d/03-perception-engine.md §0.6, §13.2). Adds or
    replaces the entry for `identity.identity_id` -- multiple identities can
    be simultaneously present (Bible Part 11's "speaker separation"), so this
    never clears the rest of the list the way `clear_present_identities`
    (presence-lost) does."""
    existing = await context_repo.get_context(user_id)
    current = list(existing.present_identities) if existing is not None else []
    remaining = [s for s in current if s.identity_id != identity.identity_id]
    remaining.append(identity)

    updated = ActiveContext(
        user_id=user_id,
        objective=existing.objective if existing is not None else None,
        project_id=existing.project_id if existing is not None else None,
        device=existing.device if existing is not None else None,
        task=existing.task if existing is not None else None,
        activity=existing.activity if existing is not None else None,
        platform=existing.platform if existing is not None else None,
        confidence=existing.confidence if existing is not None else 0.5,
        present_identities=remaining,
        updated_at=datetime.now(UTC),
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
            confidence=updated.confidence,
            present_identities=_present_identities_payload(updated),
        ).model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    await history_repo.enqueue_outbox(outbox)
    return updated


async def clear_present_identities(
    context_repo: ContextRepository,
    history_repo: WorldHistoryRepository,
    *,
    user_id: UUID,
    correlation_id: UUID,
) -> ActiveContext | None:
    """`perception.presence.observed` with `present=False` ->
    `ActiveContext.present_identities` emptied (§0.6, §13.2) -- presence lost
    means nobody currently identified is present, regardless of who was a
    moment ago; World Model represents current reality only (ADR-017), never
    a stale roster. A no-op (returns `None`) when no context row exists yet
    and the list would already be empty -- never creates a context row just
    to record an absence."""
    existing = await context_repo.get_context(user_id)
    if existing is None or not existing.present_identities:
        return None

    updated = existing.model_copy(
        update={"present_identities": [], "updated_at": datetime.now(UTC)}
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
            confidence=updated.confidence,
            present_identities=[],
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

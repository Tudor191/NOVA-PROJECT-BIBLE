"""Thought ingestion, and the one production promotion -- Phase 4F.P,
**A-4FP-1**, **A-4FP-2** and **A-4FP-10** (TDD 4F.P §30.2).

**The only production caller of `promotion_orchestration.promote_thought`.** It
sits at the package root beside `promotion_orchestration.py`, for the same
reason: it drives existing domain rules and persistence rather than defining
new ones. The `perception.workspace.observed` handler in `events/handlers.py`
invokes it and awaits it inline; `main.py` only registers that handler.

**One ingestion step, in order:**

1. **Refuse a foreign user (SD-1).** An observation whose `user_id` is not this
   engine's `primary_user_id` writes nothing.
2. **Insert the thought only if absent (A-4FP-1).** The identity is the
   observed object's (A-4FP-9), so a repeat of the same object -- a
   re-published envelope, a later observation of the same file, a second
   sensor -- gets no row back and **writes nothing and promotes nothing**.
3. **Promote exactly once, and only if this step's insert created the thought
   (A-4FP-2)**, through `promote_thought`'s compare-and-set (A-4FP-8). The
   trigger, if the move reached `IMMEDIATE`, is awaited inside that call.

**No retry, no recovery, no demotion.** If step 3 raises after step 2 created
the thought, that object's initiative is **lost**: the thought stays, the step
reports `initiative_lost`, and nothing tries again (FP-15). A trigger that is
lost in transport is reported by `DecisionTriggerPort` as a `TriggerDelivery`,
never raised, and is not retried either (A-4F6-5).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from nova_contracts.events.perception import PerceptionWorkspaceObservedPayload
from pydantic import BaseModel

from nova_cognitive_state_engine.domain.ingestion import thought_for_workspace_observation
from nova_cognitive_state_engine.domain.ports import CognitiveStateRepository, DecisionTriggerPort
from nova_cognitive_state_engine.promotion_orchestration import PromotionResult, promote_thought

__all__ = ["IngestionOutcome", "IngestionResult", "ingest_workspace_observation"]

IngestionOutcome = Literal["created", "duplicate", "foreign_user", "initiative_lost"]
"""What one ingestion step did -- four different facts:

* **`created`** -- this step inserted the thought and promoted it.
  `promotion.trigger` says what became of the trigger.
* **`duplicate`** -- the object's thought already existed. **Nothing was
  written and nothing was promoted.**
* **`foreign_user`** -- the observation named another user. **Nothing was
  written.**
* **`initiative_lost`** -- this step inserted the thought, and the promotion
  raised. The thought exists; its initiative is lost and not recovered (FP-15).
"""


class IngestionResult(BaseModel):
    outcome: IngestionOutcome
    thought_id: UUID | None = None
    """The object's thought identity. `None` only for `foreign_user`, where no
    identity was derived because nothing may be written."""

    promotion: PromotionResult | None = None
    """Only for `created`."""

    error: str | None = None
    """Only for `initiative_lost`: what the promotion raised."""


async def ingest_workspace_observation(
    payload: PerceptionWorkspaceObservedPayload,
    *,
    repository: CognitiveStateRepository,
    trigger: DecisionTriggerPort,
    user_id: UUID,
    now: datetime | None = None,
) -> IngestionResult:
    """One observation, one ingestion step. `user_id` is this engine's
    `primary_user_id`; `now` is one reading of its clock, written as the
    thought's `created_at` and `updated_at` and as the promotion's
    `updated_at`, so the whole step carries one instant.

    Raises only if the insert itself fails, in which case nothing was
    written."""
    if payload.user_id != user_id:
        return IngestionResult(outcome="foreign_user")

    instant = now if now is not None else datetime.now(UTC)
    thought = thought_for_workspace_observation(
        object_id=payload.object_id,
        label=payload.label,
        project_id=payload.project_id,
        user_id=user_id,
        now=instant,
    )

    created = await repository.insert_thought_if_absent(thought)
    if created is None:
        return IngestionResult(outcome="duplicate", thought_id=thought.thought_id)

    try:
        promotion = await promote_thought(
            created.thought_id, repository=repository, trigger=trigger, now=instant
        )
    except Exception as exc:
        # FP-15: the window between the insert and the trigger. Reported, never
        # retried -- a second attempt is exactly what A-4FP-2 rules out.
        return IngestionResult(
            outcome="initiative_lost",
            thought_id=created.thought_id,
            error=f"{type(exc).__name__}: {exc}",
        )
    return IngestionResult(outcome="created", thought_id=created.thought_id, promotion=promotion)

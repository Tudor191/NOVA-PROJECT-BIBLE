"""Promoting a thought, and the initiative trigger it can fire -- Phase 4F.6,
TDD 4F.6 §4 and §19 rows 1-2.

**The producer's application boundary.** It sits at the package root, beside
`main.py` and outside `api/` and `domain/`, following
`perception-engine/observation_orchestration.py` and
`communication-engine/conversation_orchestration.py`: it drives existing domain
rules and persistence rather than defining new ones.

**The trigger condition, exactly as ratified (A-4F6-2a):** a thought carrying a
**complete** `ProposedAction`, **promoted to `IMMEDIATE`**.

* **The transition is the existing one.** `domain.attention.next_layer` decides
  the move from its fixed ladder and `CognitiveStateRepository.move_layer`
  records it. Nothing here re-implements either. Only `ACTIVE -> IMMEDIATE`
  reaches the top, and promoting a thought that is already `IMMEDIATE` returns
  `None` from `next_layer` -- so a no-op promotion **cannot** re-fire a trigger.
* **No `ProposedAction`, no trigger.** Absence is never read as a default.
* **Every authored field is copied verbatim.** `risk` in particular is taken
  from the proposal and never derived from `confidence`, `priority`,
  `current_progress` or any Focus signal.
* **Exactly one request per qualifying promotion, and no retry** -- whatever the
  `DecisionTriggerPort` reports.

**What this module never does:** decide, execute, or name a decision's
identity. The payload carries no `subject_id` and no `user_id`;
`autonomy-engine` derives the first and resolves the second itself.

**No production caller yet -- disclosed, not hidden.** At Phase 4F.6 nothing in
this engine's running topology calls `promote_thought`: the engine exposes only
a health route, and the cognitive-state surface that would drive promotions is
**4F.7's** panel and `/v1/cognitive-state` prefix. Only its trigger port is
bound in `main.py` (`app.state.trigger`); the function itself is proven over a
real broker and real Postgres in the integration tier, which is exactly why
**CF-11 stays OPEN** after this slice.

*(Clarified 2026-09-26, Phase 4F.7 -- TDD 4F §24 RS-1b, RS-1c and RS-11. The
paragraph above is preserved as written, but "the cognitive-state surface that
would drive promotions is **4F.7's** panel and `/v1/cognitive-state` prefix" is
superseded. 4F.7 is strictly read-only: it does not create thoughts, author
`ProposedAction`s, promote, or call this function. The production promotion
driver -- with thought ingestion, `ProposedAction` authorship, CAS on the
transition and Layer 2 deduplication -- belongs to the promotion slice 4F.P,
before 4F.8. Nothing in this engine's running topology calls `promote_thought`,
and CF-11 stays OPEN.)*

*(Phase 4F.P -- TDD 4F.P §30.2, A-4FP-8 and A-4FP-10. Both notes above are
preserved as written, and two of their claims no longer hold:*

* *"`CognitiveStateRepository.move_layer` records it" is superseded. The
  transition is now recorded by `compare_and_set_layer`, one conditional
  statement that moves the thought only if it is still at the layer this call
  read. Of two concurrent promotions of one thought, exactly one moves it and
  only that one can fire the trigger; the other gets no row back and does
  nothing. `next_layer` still chooses the target, and `move_layer` is unchanged
  for callers that do not trigger.*
* *"No production caller" is superseded. `ingestion_orchestration.py` is now the
  **one** production caller (A-4FP-10): it promotes a thought exactly once, when
  its own insert created it (A-4FP-2).*

*CF-11 stays OPEN: it closes only on 4F.P's real-execution evidence, not on
this module.)*
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload
from pydantic import BaseModel

from nova_cognitive_state_engine.clients.decision_trigger_client import SOURCE_ENGINE
from nova_cognitive_state_engine.domain.attention import next_layer
from nova_cognitive_state_engine.domain.models import (
    ActiveThought,
    AttentionLayer,
    ProposedAction,
)
from nova_cognitive_state_engine.domain.ports import (
    CognitiveStateRepository,
    DecisionTriggerPort,
    TriggerDelivery,
)

__all__ = ["PromotionResult", "promote_thought", "trigger_payload"]


class PromotionResult(BaseModel):
    """What one `promote_thought` call did.

    `moved` is `False` when the ladder had nowhere to go -- the thought is
    returned unchanged and **no trigger is considered**. `trigger` is `None`
    whenever no request was sent."""

    thought: ActiveThought
    moved: bool
    trigger: TriggerDelivery | None = None


def trigger_payload(
    thought: ActiveThought, action: ProposedAction, *, correlation_id: UUID
) -> AutonomyDecisionRequestedPayload:
    """The wire payload, copied **verbatim** from the thought's authored
    proposal. Nothing is derived, defaulted or guessed; `detail` is the only
    optional field and it is optional on `ProposedAction` too."""
    return AutonomyDecisionRequestedPayload(
        thought_id=thought.thought_id,
        category=action.category,
        risk=action.risk,
        action_type=action.action_type,
        execution_target=action.execution_target,
        verification_method=action.verification_method,
        title=action.title,
        detail=action.detail,
        priority=thought.priority,
        requesting_engine=SOURCE_ENGINE,
        correlation_id=correlation_id,
    )


async def promote_thought(
    thought_id: UUID,
    *,
    repository: CognitiveStateRepository,
    trigger: DecisionTriggerPort,
    now: datetime | None = None,
) -> PromotionResult:
    """Promote one thought one step, and fire the trigger **only** if that step
    reached `IMMEDIATE` and the thought carries a complete `ProposedAction`.

    *(Phase 4F.P, A-4FP-8:)* the step is a compare-and-set. **Only the call
    whose statement moved the thought can fire the trigger**, and the trigger
    is built from the row that statement returned. `now` is the `updated_at`
    the move writes; the caller's clock reading, or this engine's clock."""
    current = await repository.get_thought(thought_id)

    target = next_layer(current.attention_layer, "promote")
    if target is None:
        # Already at the top: the ladder defines no move, so nothing moved and
        # nothing fires. This is what stops a repeated promote re-triggering.
        return PromotionResult(thought=current, moved=False)

    moved = await repository.compare_and_set_layer(
        thought_id,
        expected=current.attention_layer,
        target=target,
        updated_at=now if now is not None else datetime.now(UTC),
    )
    if moved is None:
        # A-4FP-8: another caller moved it between the read and the write, or
        # it no longer exists. That caller owns the transition and any
        # trigger; this one moved nothing and fires nothing.
        return PromotionResult(thought=current, moved=False)

    if target is not AttentionLayer.IMMEDIATE or moved.proposed_action is None:
        return PromotionResult(thought=moved, moved=True)

    correlation_id = uuid4()
    delivery = await trigger.request_decision(
        trigger_payload(moved, moved.proposed_action, correlation_id=correlation_id),
        correlation_id=correlation_id,
    )
    return PromotionResult(thought=moved, moved=True, trigger=delivery)

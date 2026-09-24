"""The repository port -- the only persistence this engine's domain knows about.

**One port, one store, and it is this engine's own.** TDD 4F §10 and §16
control 11: `cognitive-state-engine` writes its own repository and nothing
else. There is deliberately no port here for reading `memory-engine`,
`world-model-engine` or `digital-twin-engine` state -- those arrive over the
Event Bus (4F.6 onward), never through a database handle this module could be
handed.

**And no port for acting.** TDD 4F §6.2 forbids this engine from publishing
`action.execute`, calling an `action-engine` endpoint or invoking an actuator.
No method here returns or accepts anything that could express one, which is the
structural half of that prohibition; the test half is §16 control 11.

**Since Phase 4F.6 there is a second port, `DecisionTriggerPort` -- and it does
not act either.** It asks `autonomy-engine`, the control plane, to *decide* on a
thought's authored `ProposedAction` over `autonomy.decision.requested`. Whether
anything then executes is decided there, by every gate 4F.5 built, and run by
`action-engine` -- never here. *(This docstring called the repository "the only
persistence this engine's domain knows about", which remains true -- the new
port is transport, not persistence -- and described "One port" until 4F.6.
Preserved per protocol §0.3.4.)*
"""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from nova_contracts.events.autonomy import AutonomyDecisionRequestedPayload
from pydantic import BaseModel

from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer

__all__ = [
    "CognitiveStateRepository",
    "DecisionTriggerPort",
    "ThoughtNotFoundError",
    "TriggerDelivery",
    "TriggerStatus",
]

TriggerStatus = Literal["decided", "rejected", "degraded", "unavailable", "unconfirmed", "failed"]
"""What the producer **knows** about one trigger -- Phase 4F.6, A-4F6-5.

Six states because they are six different facts, and collapsing any two would
make the producer claim something it cannot know:

* **`decided`** -- `autonomy-engine` replied with an outcome. The decision was
  made and logged there.
* **`rejected`** -- `autonomy-engine` refused the payload at contract
  validation (TDD 4F.6 §9). **Nothing was decided and nothing was executed.**
* **`degraded`** -- `autonomy-engine` received the trigger and replied that it
  could not complete it. `subject_id` and `outcome` say how far it got: with
  neither, **nothing was decided or executed**; with `outcome`, a decision was
  reached but not recorded there.
* **`unavailable`** -- the broker had **no subscriber**. The request reached
  nobody, so **nothing was decided and nothing was executed**.
* **`unconfirmed`** -- **no reply in time**. The request may have been received
  and decided, and the decision may even have executed; the producer **must not
  assume otherwise**.
* **`failed`** -- an unexpected transport error. Whether the request left this
  engine is **unknown**.

**None is retried.** A retry after `unconfirmed` or `failed` could decide -- and
execute -- the same initiative twice."""


class TriggerDelivery(BaseModel):
    """The producer's record of one trigger. Returned, never raised: a lost
    trigger is an expected condition (A-4F6-5, Design A), not a crash."""

    status: TriggerStatus
    outcome: str | None = None
    """`autonomy-engine`'s `DecisionOutcome` value -- always when `status ==
    "decided"`, and on `"degraded"` only if a decision was reached but not
    recorded."""

    subject_id: UUID | None = None
    """The decision identity `autonomy-engine` derived. Read here; never
    supplied by this engine."""

    error: str | None = None


class ThoughtNotFoundError(LookupError):
    """Raised rather than returning `None` when a caller names a thought that
    does not exist. A domain error type so the API layer can map it without
    matching on exception text -- `autonomy-engine`'s own
    `SuggestionNotFoundError` convention."""


class CognitiveStateRepository(Protocol):
    """Structural, not inherited -- ADR-034's convention, so the domain never
    imports a concrete repository and `nova-service-kit` never imports this
    engine."""

    async def upsert_thought(self, thought: ActiveThought) -> ActiveThought:
        """Insert or replace by `thought_id`, returning the persisted row as it
        was read back.

        Returning the round-tripped value rather than the argument is Phase
        4E's `created_at` lesson made structural: `create_long_term` shipped
        discarding a caller's timestamps precisely because nothing compared
        what went in with what came out."""

    async def get_thought(self, thought_id: UUID) -> ActiveThought:
        """Raises `ThoughtNotFoundError` if absent."""

    async def list_thoughts(
        self, *, user_id: UUID, layer: AttentionLayer | None = None
    ) -> list[ActiveThought]:
        """Every thought for the user, newest-updated first; optionally
        narrowed to one Attention Layer.

        Ordering is `updated_at` descending with `thought_id` as an explicit
        tiebreaker, so a page boundary is reproducible across equal timestamps
        -- the property 4E's real-Postgres tier proved is not provable against
        a fake."""

    async def move_layer(self, thought_id: UUID, layer: AttentionLayer) -> ActiveThought:
        """Persist a layer change decided by `domain/attention.py`.

        **The transition rules are not re-implemented here.** This method
        records a move the domain already validated; putting `next_layer`'s
        table behind a repository call would give the ladder two definitions.
        """


class DecisionTriggerPort(Protocol):
    """Offers one thought's `ProposedAction` to `autonomy-engine` for a
    decision, over `autonomy.decision.requested`. **Phase 4F.6.**

    **One call per trigger, never retried**, and **never raises** for a
    transport condition: an implementation reports what it knows as a
    `TriggerDelivery`. The payload carries **no `subject_id` and no `user_id`**
    -- the contract has neither field."""

    async def request_decision(
        self,
        payload: AutonomyDecisionRequestedPayload,
        *,
        correlation_id: UUID,
    ) -> TriggerDelivery: ...

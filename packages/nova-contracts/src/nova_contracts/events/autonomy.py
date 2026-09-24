"""Autonomy Engine event payloads (Bible Part 14), per
docs/design/phase-4/10-tdd-4f6-initiative-trigger.md.

**`autonomy-engine` had no bus contract until Phase 4F.6**, which is the only
reason this module did not exist: every other domain with bus contracts keeps
its enums in an `events/<domain>.py` here. 4F.6's trigger gives autonomy its
first subject, so its vocabulary now has a home.

`PermissionCategory` -- A-4F6-2b, Option A
------------------------------------------
Moved here from `autonomy-engine`'s `domain/models.py`, **not copied**. It is
Bible Part 14's permission vocabulary, the sibling of `RiskLevel`
(`events/planning.py`), which is *"Bible Part 14's risk classification scale
... the one canonical risk-tier scale anywhere in this project, rather than a
second scale another engine would otherwise have to reinterpret or map"*. The
trigger puts this vocabulary on the wire, so the same reasoning now applies to
it: `cognitive-state-engine` authors a category and `autonomy-engine` evaluates
every permission gate against it, and ADR-004 forbids either importing the
other. `autonomy-engine` re-exports it through its existing `__all__`, exactly
as it already re-exports `RiskLevel`, so no call site changes.

`autonomy.decision.requested` -- A-4F6-1
----------------------------------------
**Internal, engine-to-engine, request/reply**: produced by
`cognitive-state-engine`, served by `autonomy-engine` and nothing else. It is
**never** in `PUBLIC_TOPICS`, never browser-visible and never gateway-exposed --
TDD 4F D-4F-9 (4F.6 §14) grants it as a bounded exception to TDD 4F §11.4's
*"no `autonomy.*` subject"*, which guards the browser/public surface.

**The reply payload is deliberately not registered.** Every other request/reply
pair in this package registers its reply as a subject too, and that convention
would take the registry to 121. The ratified 4F.6 contract fixes the registry at
**120** and permits exactly two contract changes, so
`AutonomyDecisionReplyPayload` is a shared model that is **not** a subject. That
is mechanically sound -- a reply travels on NATS's ephemeral inbox subject, and
neither the SDK nor the registry is consulted for it -- but it has no precedent
here, and 4F.6's completion record carries it as an open finding rather than
burying it.

Every payload carries `schema_version: int = 1` from its first commit (ADR-024).
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nova_contracts.events.action import ActionType
from nova_contracts.events.planning import RiskLevel
from nova_contracts.registry import register_payload

__all__ = [
    "AutonomyDecisionReplyPayload",
    "AutonomyDecisionRequestedPayload",
    "PermissionCategory",
]


class PermissionCategory(StrEnum):
    """Bible Part 14 "PERMISSION MATRIX" -- the ten categories, verbatim and in
    the Bible's own order. `autonomy-engine`'s `PERMISSION_CATEGORY_ORDER` pins
    the ordering separately because `StrEnum` membership alone would let a later
    edit reorder them silently.

    *(Defined in `nova_autonomy_engine.domain.models` until Phase 4F.6, and
    moved rather than copied -- A-4F6-2b. There is exactly one definition.)*"""

    READ = "read"
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    EXECUTE = "execute"
    DEPLOY = "deploy"
    PURCHASE = "purchase"
    COMMUNICATE = "communicate"


@register_payload("autonomy.decision.requested")
class AutonomyDecisionRequestedPayload(BaseModel):
    """A thought's authored `ProposedAction`, offered to `autonomy-engine` for a
    decision. **A request, never an authorization**: every gate 4F.5 built runs
    on it exactly as on any other `DecisionRequest`.

    **Two fields are absent on purpose, and a test pins both -- and unknown
    fields are rejected, so neither can be smuggled in:**

    * **No `subject_id`.** The decision's identity is derived by the consumer
      as `uuid5(namespace, str(envelope.event_id))` (A-4F6-3). A producer that
      could name it could collide with -- or replay -- a decision it did not
      make.
    * **No `user_id`.** Identity is resolved server-side from
      `primary_user_id` (TDD 4F §12); a caller-supplied `user_id` would be a
      privilege-escalation surface.

    `category`, `risk` and the three execution fields are **authored** on the
    thought and copied verbatim. `action_type` is the `action.execute` literal,
    so a value `action-engine` could never run is rejected **here**, at the
    contract boundary, instead of reaching dispatch.

    **`extra="forbid"`** -- TDD 4F.6 §9 (*"Producer-supplied `user_id`:
    **Rejected**"*) and §10's negative tier. A payload naming `user_id` or
    `subject_id` fails validation, so `decide()` is never reached with it.
    Ignoring the field silently would leave a producer believing it had steered
    something; `autonomy-engine`'s own `api/schemas.py` `_Strict` base already
    takes this position for its HTTP bodies.
    """

    model_config = ConfigDict(extra="forbid")

    thought_id: UUID
    """The thought that proposed this action -- the cognitive-state evidence
    TDD 4F §6.2 permits the producer to send."""

    category: PermissionCategory
    risk: RiskLevel
    action_type: ActionType
    execution_target: str = Field(min_length=1)
    verification_method: str = Field(min_length=1)
    title: str = Field(min_length=1)
    detail: str = ""
    priority: int = Field(default=0, ge=0)
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


class AutonomyDecisionReplyPayload(BaseModel):
    """`autonomy-engine`'s reply -- **not a registered subject** (see the module
    docstring).

    **A structured degraded reply, never a crash** (A-4F6-5, Design A): the
    same shape `world-model-engine`'s `ContextReplyPayload.degraded` and
    `capability-engine`'s failure reply already use. `degraded=True` means the
    consumer received the trigger and could not complete it, and the other two
    fields say how far it got:

    * `subject_id is None` -- it failed **before** deciding. **Nothing was
      decided and nothing was executed.**
    * `subject_id` set, `outcome is None` -- deciding **raised**. Whether an
      action ran is then as unknown as 4F.5 already leaves it for an unknown
      dispatch fault.
    * `outcome` set -- a decision was reached and **could not be recorded**.

    `rejected=True` is the other no-decision reply, and a different fact: the
    payload failed contract validation (§9, *"Malformed trigger -- rejected at
    contract validation; `decide()` not invoked"*). Design A keeps it apart from
    `degraded` because a malformed payload is a rejection, not a failure.
    """

    degraded: bool
    rejected: bool = False
    outcome: str | None = None
    """The `DecisionOutcome` value, as its string. The enum is
    `autonomy-engine`'s own and stays there; the wire carries its value."""

    subject_id: UUID | None = None
    """The consumer-derived decision identity, returned for traceability. The
    producer can **read** it here; it can never **supply** it."""

    error: str | None = None
    schema_version: int = 1

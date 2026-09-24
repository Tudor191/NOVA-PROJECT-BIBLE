"""Serving `autonomy.decision.requested` -- Phase 4F.6, TDD 4F.6 §19 rows 3-14.

**The first production caller of `decide()`, and the only one.** TDD 4F.6
A-4F6-7 places it at the application/orchestration boundary -- **not `api/`,
not `domain/`** -- and this module sits at the package root beside `main.py`,
following `perception-engine/observation_orchestration.py` and
`communication-engine/conversation_orchestration.py`. It composes what already
exists; it defines no decision rule of its own.

What it does with one envelope, in order:

1. **Validate the payload at the contract** (§9). A malformed trigger -- a
   missing field, an unknown category, or a producer-supplied `user_id` or
   `subject_id`, which `extra="forbid"` refuses -- is a **rejection**, not a
   failure. `decide()` is not invoked.
2. **Derive the decision's identity** from `envelope.event_id` (A-4F6-3,
   Layer 1). The producer never supplies it; the payload cannot carry it.
3. **Read level, policies and grants server-side**, for `primary_user_id`
   (§19 row 7). The trigger carries no level and no user, so it cannot choose
   either.
4. **Call the existing `decide()`** with the wired trust source and dispatcher.
   Every gate 4F.5 built runs unchanged; nothing here re-implements one.
5. **Record the outcome** through the repository's existing methods: a
   `propose` as a suggestion and its log row in one transaction, everything
   else as an append-only log row -- the pairing `AutonomyRepository` already
   documents.

**Design A (A-4F6-5): catch -> observe -> structured degraded reply.** Any
failure in steps 3-5 is caught here, logged with `exc_info`, and returned as
`AutonomyDecisionReplyPayload(degraded=True)` -- the shape `world-model-engine`'s
`ContextReplyPayload.degraded` and `capability-engine`'s failure reply already
use. **No retry at any step**, no new `DecisionOutcome`, no audit table. The
reply says how far the attempt got, because those are different facts:

* `subject_id is None` -- the failure came **before** `decide()`; nothing was
  decided and nothing was executed.
* `subject_id` set, `outcome is None` -- `decide()` **raised**. The one way it
  can raise after dispatching is an unknown transport fault on `action.execute`,
  which 4F.5 deliberately propagates rather than naming; in that case whether
  `action-engine` ran the action is unknown, exactly as it was in 4F.5.
* `outcome` set -- `decide()` **returned**, and recording it failed. If the
  outcome is `execute`, the action was dispatched.

**Not deduplication beyond Layer 1** (§19 row 8). Two envelopes with different
`event_id`s are two decisions. A redelivered envelope derives the same
`subject_id`: a re-dispatch reaches `action-engine`'s existing terminal-replay
guard under the same `action_id`, and a second `propose` is refused by the
suggestion table's existing primary key -- its transaction rolls back whole, and
the attempt is reported through the degraded reply like any other recording
failure. **No constraint, no migration and no second mechanism is added.**
"""

from __future__ import annotations

from uuid import UUID, uuid5

from nova_contracts import EventEnvelope
from nova_contracts.events.autonomy import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
)
from nova_observability import get_logger
from pydantic import ValidationError

from nova_autonomy_engine.domain.decision import DecisionRequest, DecisionResult, decide
from nova_autonomy_engine.domain.models import AutonomyLevel, DecisionOutcome
from nova_autonomy_engine.domain.ports import (
    ActionDispatchPort,
    AutonomyRepository,
    ConversationalTrustSource,
)

__all__ = [
    "DECISION_TRIGGER_SUBJECT",
    "decision_request",
    "derive_subject_id",
    "handle_decision_request",
]

DECISION_TRIGGER_SUBJECT = "autonomy.decision.requested"
"""The one subject this engine serves -- named here so the serve call in
`main.py` and `events/subscribed.py` cannot drift apart silently."""

_DECISION_TRIGGER_NAMESPACE = UUID("0c81f3b8-e30f-5f0a-9241-8985e4b83489")
"""**A-4F6-3 Layer 1, TDD 4F.6 §5.2 -- pinned, never generated at runtime.**

Mirrors `digital-twin-engine`'s `_ATTENTION_NAMESPACE`. Its provenance is
reproducible -- `uuid5(NAMESPACE_DNS, "autonomy.decision.requested.nova")` --
but the **literal** is what is pinned: changing it would silently give every
redelivered trigger a new identity, and a test fails if it moves."""

_UNCONFIGURED_LEVEL = AutonomyLevel.OBSERVATION_ONLY
"""What an unconfigured instance decides at -- the same Level 0 `api/autonomy.py`
reports for a user who never set one (TDD 4D §19). A trigger arriving before
anyone configured autonomy is therefore observed, never proposed or executed."""

logger = get_logger("autonomy-engine")


def derive_subject_id(event_id: UUID) -> UUID:
    """`uuid5(_DECISION_TRIGGER_NAMESPACE, str(event_id))` -- **§19 row 3.**

    The input is the envelope's `event_id` **and nothing else**: not
    `occurred_at`, not `correlation_id`, not any payload field. The same
    envelope redelivered derives the same id; two envelopes with identical
    payloads derive two."""
    return uuid5(_DECISION_TRIGGER_NAMESPACE, str(event_id))


def decision_request(
    payload: AutonomyDecisionRequestedPayload, *, user_id: UUID
) -> DecisionRequest:
    """The trigger as the existing `DecisionRequest`, field for field.

    `user_id` is **this engine's** `primary_user_id`, passed in by the caller --
    the payload has no such field (§19 row 7). `capability_class` stays `None`:
    the trigger does not carry one, and a policy that matches on it therefore
    does not match, which is the fail-closed direction."""
    return DecisionRequest(
        user_id=user_id,
        category=payload.category,
        risk=payload.risk,
        title=payload.title,
        detail=payload.detail,
        priority=payload.priority,
        action_type=payload.action_type,
        execution_target=payload.execution_target,
        verification_method=payload.verification_method,
    )


async def _record(result: DecisionResult, repository: AutonomyRepository) -> None:
    """The persistence pairing `AutonomyRepository` already documents: a
    proposal and its log row in one transaction, every other outcome as one
    append-only log row."""
    if result.outcome is DecisionOutcome.PROPOSE and result.suggestion is not None:
        await repository.insert_suggestion(result.suggestion, result.log_entry)
    else:
        await repository.append_decision_log(result.log_entry)


async def handle_decision_request(
    envelope: EventEnvelope,
    *,
    repository: AutonomyRepository,
    trust_source: ConversationalTrustSource,
    dispatcher: ActionDispatchPort | None,
    user_id: UUID,
) -> AutonomyDecisionReplyPayload:
    """Serve one `autonomy.decision.requested`. **Never raises** -- every path
    returns a structured reply (Design A)."""
    try:
        payload = AutonomyDecisionRequestedPayload.model_validate(envelope.payload)
    except ValidationError as exc:
        logger.warning(
            "autonomy.decision.requested rejected at contract validation: "
            "event_id=%s correlation_id=%s errors=%d; decide() not invoked",
            envelope.event_id,
            envelope.correlation_id,
            exc.error_count(),
        )
        return AutonomyDecisionReplyPayload(
            degraded=False,
            rejected=True,
            error=f"payload failed contract validation ({exc.error_count()} error(s))",
        )

    subject_id = derive_subject_id(envelope.event_id)

    try:
        setting = await repository.get_level(user_id)
        policies = await repository.list_policies(user_id)
        grants = await repository.list_permission_grants(user_id)
    except Exception as exc:  # noqa: BLE001 -- structured reply, never a crash (A-4F6-5)
        logger.warning(
            "autonomy.decision.requested degraded before decide(): event_id=%s "
            "correlation_id=%s; nothing was decided or executed, and this is not "
            "retried",
            envelope.event_id,
            envelope.correlation_id,
            exc_info=True,
        )
        return AutonomyDecisionReplyPayload(degraded=True, error=f"{type(exc).__name__}: {exc}")

    level = setting.level if setting is not None else _UNCONFIGURED_LEVEL

    try:
        result = await decide(
            decision_request(payload, user_id=user_id),
            level=level,
            policies=policies,
            grants=grants,
            trust_source=trust_source,
            dispatcher=dispatcher,
            subject_id=subject_id,
        )
    except Exception as exc:  # noqa: BLE001 -- structured reply, never a crash (A-4F6-5)
        logger.warning(
            "autonomy.decision.requested degraded: decide() raised for subject %s "
            "(event_id=%s correlation_id=%s); nothing is retried",
            subject_id,
            envelope.event_id,
            envelope.correlation_id,
            exc_info=True,
        )
        return AutonomyDecisionReplyPayload(
            degraded=True, subject_id=subject_id, error=f"{type(exc).__name__}: {exc}"
        )

    try:
        await _record(result, repository)
    except Exception as exc:  # noqa: BLE001 -- structured reply, never a crash (A-4F6-5)
        logger.warning(
            "autonomy.decision.requested degraded: decided %s for subject %s but "
            "could not record it (event_id=%s correlation_id=%s); nothing is retried",
            result.outcome.value,
            subject_id,
            envelope.event_id,
            envelope.correlation_id,
            exc_info=True,
        )
        return AutonomyDecisionReplyPayload(
            degraded=True,
            outcome=result.outcome.value,
            subject_id=subject_id,
            error=f"{type(exc).__name__}: {exc}",
        )

    return AutonomyDecisionReplyPayload(
        degraded=False, outcome=result.outcome.value, subject_id=subject_id
    )

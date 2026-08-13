"""Fork D's warm-case proactive delivery orchestration (docs/design/
phase-2d/06-personal-companion.md Sec10.2) -- the one genuinely new
synchronous caller this engine adds this phase. Composes three
already-existing/already-approved pieces: `domain.proactive_boundary.
evaluate_proactive_suggestion` (the policy, Sec10.1), the new `user_id ->
connected session_id` lookup, and the existing, already-tested
`communication.intent.deliver.request` gate (ADR-005) -- no new heuristic,
no new delivery mechanism (Sec1.1's own finding).

Lives outside `domain/` because it performs I/O (repository reads/writes, a
synchronous cross-engine RPC) -- mirrors `communication-engine`'s own
`conversation_orchestration.py` placement for the identical reason.

No production call site invokes this function yet -- Sec10's own scope is
the policy and the delivery mechanism, not a scheduler or trigger source
for *when* a proactive suggestion is proposed (out of this phase's approved
scope; no such source exists anywhere in this codebase). This mirrors the
established, disclosed precedent for `domain.response_shaping.
resolve_response_shaping`'s own optional `digital_twin_port` in
communication-engine: real, fully tested, callable, but not yet wired to a
production trigger.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import FastAPI

from nova_digital_twin_engine.domain.models import (
    ProactiveBoundaryPolicy,
    ProactiveDeliveryRecord,
    ProactiveSuggestion,
)
from nova_digital_twin_engine.domain.proactive_boundary import evaluate_proactive_suggestion

__all__ = ["attempt_proactive_delivery"]


async def attempt_proactive_delivery(
    app: FastAPI,
    *,
    user_id: UUID,
    suggestion: ProactiveSuggestion,
    now: datetime | None = None,
) -> ProactiveDeliveryRecord | None:
    """`None` covers every non-delivery outcome (denied by policy, no
    connected session -- Sec10.3's cold case -- the intent gate itself
    declining to deliver, or a communication-engine timeout) -- Sec10.2
    step 4's "no delivery is attempted... simply not deliverable" applies
    identically to all of them; the caller does not need to distinguish
    them to know nothing was sent."""
    state = app.state
    resolved_now = now or datetime.now(UTC)

    policy = await state.repository.get_proactive_boundary_policy(user_id)
    if policy is None:
        # Sec10.1's own fail-closed discipline: an unconfigured policy has
        # no per-topic limit, so `evaluate_proactive_suggestion` naturally
        # denies every topic without this function special-casing it.
        policy = ProactiveBoundaryPolicy(user_id=user_id)

    window_start = resolved_now - timedelta(hours=policy.window_hours)
    recent = await state.repository.list_recent_proactive_deliveries(
        user_id, since=window_start
    )

    decision = evaluate_proactive_suggestion(
        policy=policy, suggestion=suggestion, recent_deliveries=recent, now=resolved_now
    )
    state.metrics.proactive_suggestion_decisions_total.add(
        1, {"outcome": "allowed" if decision.allowed else "denied"}
    )
    if not decision.allowed:
        return None

    try:
        session_id = await state.communication_port.get_connected_session(user_id=user_id)
    except TimeoutError:
        return None
    if session_id is None:
        return None

    try:
        delivered = await state.communication_port.deliver_intent(
            session_id=session_id, content=suggestion.content
        )
    except TimeoutError:
        return None
    if not delivered:
        return None

    record = ProactiveDeliveryRecord(
        user_id=user_id, topic=suggestion.topic, delivered_at=resolved_now
    )
    return await state.repository.record_proactive_delivery(record)

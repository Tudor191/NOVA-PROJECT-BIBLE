"""`DecisionTriggerClient` -- `domain.ports.DecisionTriggerPort` over the Event
Bus. **The producer side of `autonomy.decision.requested`** (TDD 4F.6 §3, §9.1).

**This is the producer-side error boundary, and it is where the ratified
Design A (A-4F6-5) lives for this engine**: catch, observe, and return a
structured result -- never a crash, and never a retry. It is the same shape the
repository's catching serve handlers already use (`capability-engine`'s
*"structured reply, never a crash"*, `world-model-engine`'s `degraded` reply),
applied to the side that sends rather than the side that serves.

**`NoRespondersError` is handled here because it is raised here.** When nothing
serves `autonomy.decision.requested`, NATS answers the *requester* immediately.
The SDK translates its own `TimeoutError` into the builtin but not this one
(**L-18**, owned by `nova-eventbus-sdk` and deliberately not fixed in 4F.6), so
it arrives as a raw `nats.errors.NoRespondersError`. It is recognised **by type
name**: `nats` is not a dependency of this engine, and import-linter's ADR-006
contract forbids any engine importing a broker client -- the same reasoning, and
the same technique, as `autonomy-engine`'s 4F.5 `ActionDispatchClient`. A real
broker test proves the name still matches.

**The five no-decision outcomes are kept apart** because they are different facts
(see `domain.ports.TriggerStatus`): no subscriber means nothing happened; no
reply in time means something may have.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts.events.autonomy import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
)
from nova_observability import get_logger

from nova_cognitive_state_engine.domain.ports import TriggerDelivery

__all__ = ["DECISION_TRIGGER_SUBJECT", "SOURCE_ENGINE", "DecisionTriggerClient"]

SOURCE_ENGINE = "cognitive-state-engine"

DECISION_TRIGGER_SUBJECT = "autonomy.decision.requested"
"""The one subject this engine may put on the bus -- named here so the trigger
path and `events/published.py` cannot drift apart silently."""

_NO_RESPONDERS = "NoRespondersError"

logger = get_logger("cognitive-state-engine")


def _is_no_responders(exc: BaseException) -> bool:
    return type(exc).__name__ == _NO_RESPONDERS


class DecisionTriggerClient:
    """Adapter from `DecisionTriggerPort` to `BoundEventBus.request`.

    Typed against the bus structurally rather than importing `BoundEventBus`,
    so the unit tier can drive it without a broker -- `autonomy-engine`'s
    `ActionDispatchClient` convention."""

    def __init__(self, bus: object, *, timeout_seconds: float) -> None:
        self._bus = bus
        self._timeout_seconds = timeout_seconds

    async def request_decision(
        self,
        payload: AutonomyDecisionRequestedPayload,
        *,
        correlation_id: UUID,
    ) -> TriggerDelivery:
        """**Exactly one request. No retry on any outcome.**"""
        try:
            reply = await self._bus.request(  # type: ignore[attr-defined]
                DECISION_TRIGGER_SUBJECT,
                payload,
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=int(self._timeout_seconds * 1000),
            )
        except TimeoutError:
            logger.warning(
                "autonomy.decision.requested unconfirmed: no reply within %ss for "
                "thought %s; autonomy-engine may still have decided, and this is "
                "not retried",
                self._timeout_seconds,
                payload.thought_id,
            )
            return TriggerDelivery(
                status="unconfirmed",
                error=f"no reply within {self._timeout_seconds}s; not retried",
            )
        except Exception as exc:
            if _is_no_responders(exc):
                logger.warning(
                    "autonomy.decision.requested unavailable: no subscriber for "
                    "thought %s; nothing was decided or executed, and this is not "
                    "retried",
                    payload.thought_id,
                )
                return TriggerDelivery(
                    status="unavailable",
                    error="no subscriber on autonomy.decision.requested; not retried",
                )
            logger.warning(
                "autonomy.decision.requested failed for thought %s; delivery state "
                "unknown, and this is not retried",
                payload.thought_id,
                exc_info=True,
            )
            return TriggerDelivery(status="failed", error=f"{type(exc).__name__}: {exc}")

        parsed = AutonomyDecisionReplyPayload.model_validate(reply.payload)
        if parsed.rejected:
            logger.warning(
                "autonomy.decision.requested rejected for thought %s: %s",
                payload.thought_id,
                parsed.error,
            )
            return TriggerDelivery(status="rejected", error=parsed.error)
        if parsed.degraded:
            logger.warning(
                "autonomy.decision.requested degraded for thought %s: %s",
                payload.thought_id,
                parsed.error,
            )
            return TriggerDelivery(
                status="degraded",
                outcome=parsed.outcome,
                subject_id=parsed.subject_id,
                error=parsed.error,
            )
        return TriggerDelivery(
            status="decided", outcome=parsed.outcome, subject_id=parsed.subject_id
        )

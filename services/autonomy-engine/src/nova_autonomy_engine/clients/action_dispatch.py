"""`ActionDispatchClient` -- `domain.ports.ActionDispatchPort` over the Event
Bus. **`action.execute`'s first producer** (TDD 4F.5 §8, TDD 4F §11.2).

`action.execute` has been a registered contract served by `action-engine` since
Phase 3D with **no production publisher**. 4F.5 makes `autonomy-engine` its
first, which is the same *new-producer-on-an-existing-contract* shape 4E used:
**no new subject is registered**, and the registry stays at 119.

**`.request()`, never `.publish()`.** `action.execute` is request/reply --
`nova_contracts.events.action`: *"the request/reply RPC `action-engine` serves
now"* -- with `ActionResultPayload` as its reply. Publishing it would throw the
reply away on a subject that has one, and the decision log would then record an
execution it never saw confirmed. `BoundEventBus` enforces the same
`PUBLISHABLE_SUBJECTS` allow-list for both, so the allow-list entry does not by
itself choose the shape; this module does.

**The 15-second bound is this call's alone** (D-4F5-3). It is not the SDK's
default, not a global setting, and emphatically not `action-engine`'s own
300-second approval-loop timeout, which is untouched. A LOW-risk
policy-permitted action should never reach that loop; if something stalls
anyway, the control plane degrades to a recorded timeout instead of hanging.

**No retry, no queue, no scheduler.** One qualifying decision issues at most one
request. A retry would risk double-executing an action whose first attempt
actually succeeded and merely replied late -- `action-engine`'s idempotency
guard is keyed on a caller-supplied `action_id`, and re-sending the same id
would be a *deliberate* retry rather than an accident, which is precisely what
D-4F5-3 forbids here.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import ActionExecuteRequestPayload, ActionResultPayload

from nova_autonomy_engine.domain.ports import (
    ActionDispatchResult,
    ActionDispatchTimeout,
    ActionDispatchUnavailable,
)

__all__ = ["ACTION_EXECUTE_SUBJECT", "SOURCE_ENGINE", "ActionDispatchClient"]

SOURCE_ENGINE = "autonomy-engine"

ACTION_EXECUTE_SUBJECT = "action.execute"
"""The one subject this engine may put on the bus. Named here so the dispatch
path and `events/published.py` cannot drift apart silently."""

_NO_RESPONDERS = "NoRespondersError"
"""The broker's zero-subscriber signal, matched **by type name**.

The SDK translates the transport's `TimeoutError` into the builtin at
`backends/nats.py`, but it does **not** translate this one, so the raw
`nats.errors.NoRespondersError` escapes the abstraction (**L-18**, opened
2026-09-21 and owned by `nova-eventbus-sdk`). Until L-18 is settled this
adapter must recognise it here.

**Matched structurally rather than imported on purpose.** `nats` is not a
declared dependency of this engine -- only `nova-eventbus-sdk` is -- and
importing the broker library would put transport knowledge inside a service
that is supposed to see only `BoundEventBus`. The cost of a name match is that
a rename upstream would slip past it, which is exactly why
`test_a_real_broker_with_no_responder_is_reported_unavailable` drives this
branch against a **real** NATS broker rather than a constructed exception."""


def _is_no_responders(exc: BaseException) -> bool:
    """Is this the broker saying *nobody is subscribed*? See `_NO_RESPONDERS`."""
    return type(exc).__name__ == _NO_RESPONDERS


class ActionDispatchClient:
    """Adapter from `ActionDispatchPort` to `BoundEventBus.request`.

    Typed against the bus structurally rather than importing `BoundEventBus`:
    `domain/` may not import `nova_eventbus_sdk`, and keeping the dependency
    duck-typed lets the unit tier drive this class without a bus at all.
    """

    def __init__(self, bus: object, *, timeout_seconds: float) -> None:
        self._bus = bus
        self._timeout_seconds = timeout_seconds

    async def dispatch(
        self,
        payload: ActionExecuteRequestPayload,
        *,
        correlation_id: UUID | None = None,
    ) -> ActionDispatchResult:
        """One request, one reply, or one of **two distinct** typed failures.

        `TimeoutError` is translated rather than propagated so that callers
        distinguish *"no reply in time"* from any other failure without
        matching on a builtin -- and so `decide()` can record
        `DecisionOutcome.TIMEOUT` rather than letting a transport detail decide
        a security-relevant outcome's name.

        **`ActionDispatchUnavailable` is the other one, and it is not a
        timeout** (ratified 2026-09-21). A broker with no subscriber answers
        immediately, not after 15 seconds, and the action provably never ran.
        Recording that as a timeout would claim the action *may* have executed.
        *(This docstring read "One request, one reply, or
        `ActionDispatchTimeout`" until that pass; preserved per protocol
        §0.3.4.)*
        """
        try:
            reply = await self._bus.request(  # type: ignore[attr-defined]
                ACTION_EXECUTE_SUBJECT,
                payload,
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=int(self._timeout_seconds * 1000),
            )
        except TimeoutError as exc:
            raise ActionDispatchTimeout(
                f"no reply to {ACTION_EXECUTE_SUBJECT} for action "
                f"{payload.action_id} within {self._timeout_seconds}s; the "
                f"action may still have executed, and this is not retried"
            ) from exc
        except Exception as exc:
            # Only the zero-subscriber signal is claimed here. Anything else is
            # an unknown transport fault and must keep its own identity rather
            # than be dressed up as a dispatch condition this engine models.
            if not _is_no_responders(exc):
                raise
            raise ActionDispatchUnavailable(
                f"no subscriber on {ACTION_EXECUTE_SUBJECT} for action "
                f"{payload.action_id}; the request reached nobody, so the "
                f"action was not executed, and this is not retried"
            ) from exc

        parsed = ActionResultPayload.model_validate(reply.payload)
        return ActionDispatchResult(
            action_id=parsed.action_id, status=str(parsed.status), error=parsed.error
        )

"""`ActionDispatchClient` — the `action.execute` adapter. **Phase 4F.5**,
TDD 4F.5 §8 and D-4F5-3.

What this file decides is the adapter's *contract with the bus*: the method it
calls, the subject it names, the timeout it passes and the exception it
raises. What it deliberately does **not** decide is whether the transport
works — that is proven against a real NATS broker in
`tests/integration/test_level_two_real_postgres.py`.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from nova_autonomy_engine.clients.action_dispatch import (
    ACTION_EXECUTE_SUBJECT,
    ActionDispatchClient,
)
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.domain.ports import ActionDispatchTimeout
from nova_contracts import ActionExecuteRequestPayload, ActionResultPayload
from pydantic import BaseModel


class _Envelope(BaseModel):
    payload: dict


class RecordingBus:
    """Records how the adapter called `request`, and fails loudly if it ever
    reaches for `publish` instead."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._raises = raises

    async def request(
        self,
        subject: str,
        payload: BaseModel,
        *,
        source_engine: str,
        correlation_id: UUID | None = None,
        timeout_ms: int = 2000,
    ) -> _Envelope:
        self.calls.append(
            {
                "subject": subject,
                "source_engine": source_engine,
                "correlation_id": correlation_id,
                "timeout_ms": timeout_ms,
            }
        )
        if self._raises is not None:
            raise self._raises
        reply = ActionResultPayload(
            action_id=payload.action_id,  # type: ignore[attr-defined]
            status="completed",
        )
        return _Envelope(payload=reply.model_dump(mode="json"))

    async def publish(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "action.execute is request/reply; publish() would discard the reply"
        )


def _payload() -> ActionExecuteRequestPayload:
    return ActionExecuteRequestPayload(
        action_id=uuid4(),
        action_type="filesystem",
        priority="normal",
        source="autonomy-engine",
        requested_by=uuid4(),
        execution_target="filesystem",
        verification_method="none",
        requesting_engine="autonomy-engine",
        correlation_id=uuid4(),
    )


async def test_it_requests_action_execute_and_returns_the_reply() -> None:
    bus = RecordingBus()
    payload = _payload()

    result = await ActionDispatchClient(bus, timeout_seconds=15.0).dispatch(payload)

    assert bus.calls[0]["subject"] == ACTION_EXECUTE_SUBJECT == "action.execute"
    assert bus.calls[0]["source_engine"] == "autonomy-engine"
    assert result.action_id == payload.action_id
    assert result.status == "completed"


async def test_the_fifteen_second_bound_is_converted_to_milliseconds() -> None:
    """**D-4F5-3.** The SDK takes milliseconds; the setting is in seconds, and
    a silent factor-of-1000 error would turn a 15-second bound into 15
    milliseconds — which would look like a flaky broker rather than a bug."""
    bus = RecordingBus()

    await ActionDispatchClient(bus, timeout_seconds=15.0).dispatch(_payload())

    assert bus.calls[0]["timeout_ms"] == 15_000


def test_fifteen_seconds_is_the_production_default() -> None:
    """The ratified number, pinned where a change becomes a deliberate act."""
    assert Settings().action_execute_timeout_seconds == 15.0


def test_the_bound_is_far_below_action_engines_approval_loop() -> None:
    """**The gap is the point** (D-4F5-3): a stalled dispatch degrades to a
    recorded timeout instead of the control plane blocking on a loop it has no
    business waiting for. `action-engine`'s own 300 s default is **not
    changed** by this slice — it is read here only as the comparison."""
    assert Settings().action_execute_timeout_seconds < 300.0


async def test_a_transport_timeout_becomes_the_typed_exception() -> None:
    """A caller must never have to match on a builtin `TimeoutError` to tell a
    bounded wait from any other failure."""
    bus = RecordingBus(raises=TimeoutError("nats request timed out"))

    with pytest.raises(ActionDispatchTimeout, match="no reply"):
        await ActionDispatchClient(bus, timeout_seconds=15.0).dispatch(_payload())


async def test_the_timeout_message_does_not_claim_the_action_failed() -> None:
    """`action-engine` may have executed the action and replied late. The
    message says what was observed and nothing more."""
    bus = RecordingBus(raises=TimeoutError("nats request timed out"))

    with pytest.raises(ActionDispatchTimeout) as caught:
        await ActionDispatchClient(bus, timeout_seconds=15.0).dispatch(_payload())

    message = str(caught.value).lower()
    assert "may still have executed" in message
    assert "not retried" in message


async def test_one_dispatch_issues_exactly_one_request() -> None:
    """No retry inside the adapter, on success or on timeout."""
    bus = RecordingBus()
    await ActionDispatchClient(bus, timeout_seconds=15.0).dispatch(_payload())
    assert len(bus.calls) == 1

    timing_out = RecordingBus(raises=TimeoutError("nats request timed out"))
    with pytest.raises(ActionDispatchTimeout):
        await ActionDispatchClient(timing_out, timeout_seconds=15.0).dispatch(_payload())
    assert len(timing_out.calls) == 1

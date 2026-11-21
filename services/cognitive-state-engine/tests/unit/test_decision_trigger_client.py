"""`DecisionTriggerClient` -- the producer-side error boundary, Phase 4F.6
(A-4F6-5 Design A; TDD 4F.6 §19 rows 10-12).

**Six outcomes, kept apart.** Each test drives one of them through a fake bus
that records every call, because the two properties that matter most -- *one
request* and *no exception escapes* -- are facts about this adapter, not about
the transport. The real-broker halves (a genuine `NoRespondersError`, a genuine
elapsed timeout) are in `tests/integration/test_decision_trigger_real_nats.py`.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from nova_cognitive_state_engine.clients.decision_trigger_client import (
    DECISION_TRIGGER_SUBJECT,
    SOURCE_ENGINE,
    DecisionTriggerClient,
)
from nova_cognitive_state_engine.config import Settings
from nova_cognitive_state_engine.events.published import PUBLISHABLE_SUBJECTS
from nova_contracts import EventEnvelope
from nova_contracts.events.autonomy import (
    AutonomyDecisionReplyPayload,
    AutonomyDecisionRequestedPayload,
)


class NoRespondersError(Exception):
    """Named exactly as `nats.errors.NoRespondersError`. The adapter matches by
    type name, so this reproduces the branch; the real class is exercised
    against a real broker in the integration tier."""


class FakeBus:
    def __init__(self, *, reply: AutonomyDecisionReplyPayload | None = None, raises=None) -> None:  # type: ignore[no-untyped-def]
        self.calls: list[dict] = []
        self._reply = reply
        self._raises = raises

    async def request(self, subject: str, payload, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"subject": subject, "payload": payload, **kwargs})
        if self._raises is not None:
            raise self._raises
        assert self._reply is not None
        return EventEnvelope(
            subject="_INBOX.x",
            source_engine="autonomy-engine",
            correlation_id=kwargs["correlation_id"],
            payload=self._reply.model_dump(mode="json"),
        )


def _payload() -> AutonomyDecisionRequestedPayload:
    return AutonomyDecisionRequestedPayload(
        thought_id=uuid4(),
        category="create",
        risk="low",
        action_type="filesystem",
        execution_target="filesystem",
        verification_method="none",
        title="rotate the scratch directory",
        requesting_engine=SOURCE_ENGINE,
        correlation_id=uuid4(),
    )


async def _send(bus: FakeBus, *, timeout_seconds: float = 20.0):  # type: ignore[no-untyped-def]
    payload = _payload()
    delivery = await DecisionTriggerClient(bus, timeout_seconds=timeout_seconds).request_decision(
        payload, correlation_id=payload.correlation_id
    )
    return payload, delivery


# --- the request itself ------------------------------------------------------------


async def test_one_request_on_the_one_subject_with_the_bound_in_milliseconds() -> None:
    subject_id = uuid4()
    bus = FakeBus(
        reply=AutonomyDecisionReplyPayload(degraded=False, outcome="propose", subject_id=subject_id)
    )
    payload, delivery = await _send(bus)

    assert len(bus.calls) == 1
    call = bus.calls[0]
    assert call["subject"] == DECISION_TRIGGER_SUBJECT == "autonomy.decision.requested"
    assert call["subject"] in PUBLISHABLE_SUBJECTS
    assert call["payload"] is payload
    assert call["source_engine"] == "cognitive-state-engine"
    assert call["correlation_id"] == payload.correlation_id
    assert call["timeout_ms"] == 20_000
    assert delivery.status == "decided"
    assert delivery.outcome == "propose"
    assert delivery.subject_id == subject_id


def test_the_reply_bound_defaults_to_twenty_seconds_and_exceeds_dispatchs_fifteen() -> None:
    """**An unratified implementation parameter, disclosed as such.** It must
    exceed `autonomy-engine`'s 15-second dispatch bound, because the reply can
    follow a dispatch; it is a reply wait, not a TTL (A-4F6-4 stays OPEN)."""
    assert Settings().decision_trigger_timeout_seconds == 20.0
    assert Settings().decision_trigger_timeout_seconds > 15.0


# --- the six outcomes -------------------------------------------------------------


async def test_a_rejected_reply_is_reported_as_rejected() -> None:
    bus = FakeBus(reply=AutonomyDecisionReplyPayload(degraded=False, rejected=True, error="bad"))
    _, delivery = await _send(bus)
    assert delivery.status == "rejected"
    assert delivery.outcome is None
    assert len(bus.calls) == 1


async def test_a_degraded_reply_is_reported_with_whatever_it_carries() -> None:
    subject_id: UUID = uuid4()
    bus = FakeBus(
        reply=AutonomyDecisionReplyPayload(
            degraded=True, outcome="execute", subject_id=subject_id, error="not recorded"
        )
    )
    _, delivery = await _send(bus)
    assert delivery.status == "degraded"
    assert delivery.outcome == "execute"
    assert delivery.subject_id == subject_id
    assert len(bus.calls) == 1


async def test_no_responders_is_unavailable_and_not_retried() -> None:
    bus = FakeBus(raises=NoRespondersError("nats: no responders available for request"))
    _, delivery = await _send(bus)
    assert delivery.status == "unavailable"
    assert delivery.outcome is None
    assert len(bus.calls) == 1


async def test_a_timeout_is_unconfirmed_not_failed_and_not_retried() -> None:
    """After a timeout the consumer **may** have decided -- and executed. The
    producer must not claim otherwise, and must not send again."""
    bus = FakeBus(raises=TimeoutError("No reply on 'autonomy.decision.requested'"))
    _, delivery = await _send(bus)
    assert delivery.status == "unconfirmed"
    assert delivery.status != "failed"
    assert len(bus.calls) == 1


async def test_an_unexpected_transport_error_is_failed_and_not_retried() -> None:
    bus = FakeBus(raises=ConnectionResetError("broker went away"))
    _, delivery = await _send(bus)
    assert delivery.status == "failed"
    assert delivery.error is not None
    assert "ConnectionResetError" in delivery.error
    assert len(bus.calls) == 1


@pytest.mark.parametrize(
    "raises",
    [TimeoutError("t"), NoRespondersError("n"), RuntimeError("r"), OSError("o")],
)
async def test_no_transport_exception_escapes(raises: Exception) -> None:
    """Design A: a lost trigger is an expected condition, returned -- never a
    crash in the promotion path."""
    _, delivery = await _send(FakeBus(raises=raises))
    assert delivery.status in {"unavailable", "unconfirmed", "failed"}

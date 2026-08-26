"""A real Event Bus round-trip through `main.py`'s served
`agent_os.supervisor.peer_review.request` RPC (disclosed addition, see
`events/peer_review_record_handler.py`'s own docstring) -- mirrors
`test_events_restart_plan_request.py`'s own convention exactly.

`app.state.bus`'s own `publishable_subjects` deliberately do not include
this subject -- Supervisors only ever *serves* it, never calls it on
itself. A second `BoundEventBus`, wrapping the exact same underlying
in-memory bus instance, stands in for the real external caller
(`agent-os/kernel`'s own Scheduler).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from nova_agent_os_supervisors.config import Settings
from nova_agent_os_supervisors.main import create_app
from nova_contracts import (
    AgentOsPeerReviewReplyPayload,
    AgentOsPeerReviewRequestPayload,
    AgentResult,
)
from nova_eventbus_sdk import BoundEventBus


def _caller_bus(app):  # type: ignore[no-untyped-def]
    return BoundEventBus(
        app.state.bus._bus,  # noqa: SLF001 -- same in-memory broker as the app's own bus
        engine_name="test-caller-engine",
        publishable_subjects=frozenset({"agent_os.supervisor.peer_review.request"}),
        subscribable_subjects=frozenset(),
    )


def _result(**overrides: object) -> AgentResult:
    defaults: dict[str, object] = {
        "agent_instance_id": uuid4(),
        "task_node_id": uuid4(),
        "status": "success",
        "output": {"summary": "coding-agent's work"},
        "confidence": 0.9,
        "self_validation_passed": True,
        "correlation_id": uuid4(),
    }
    defaults.update(overrides)
    return AgentResult(**defaults)


class _RecordingDecisionMemoryPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def record(
        self,
        *,
        objective: str,
        alternatives: list[str],
        chosen_alternative: str,
        reasoning: str,
        correlation_id: UUID,
    ) -> None:
        self.calls.append(
            {
                "objective": objective,
                "alternatives": alternatives,
                "chosen_alternative": chosen_alternative,
                "correlation_id": correlation_id,
            }
        )


async def test_peer_review_approved_records_and_replies_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    decision_memory = _RecordingDecisionMemoryPort()
    app = create_app(Settings(), decision_memory_port=decision_memory)
    primary = _result()
    reviewer = _result(status="success")
    correlation_id = uuid4()

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsPeerReviewRequestPayload(
            primary_result=primary,
            reviewer_category="architect",
            reviewer_result=reviewer,
            reviewer_available=True,
            requesting_engine="test-caller-engine",
            correlation_id=correlation_id,
        )
        reply_envelope = await caller_bus.request(
            "agent_os.supervisor.peer_review.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsPeerReviewReplyPayload.model_validate(reply_envelope.payload)

    assert result.peer_validation == "approved"
    assert len(decision_memory.calls) == 1
    assert decision_memory.calls[0]["correlation_id"] == correlation_id


async def test_peer_review_rejected_records_and_replies_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    decision_memory = _RecordingDecisionMemoryPort()
    app = create_app(Settings(), decision_memory_port=decision_memory)
    primary = _result()
    reviewer = _result(status="needs_revision")

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsPeerReviewRequestPayload(
            primary_result=primary,
            reviewer_category="architect",
            reviewer_result=reviewer,
            reviewer_available=True,
            requesting_engine="test-caller-engine",
            correlation_id=uuid4(),
        )
        reply_envelope = await caller_bus.request(
            "agent_os.supervisor.peer_review.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsPeerReviewReplyPayload.model_validate(reply_envelope.payload)

    assert result.peer_validation == "rejected"


async def test_peer_review_unavailable_reviewer_replies_timed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    decision_memory = _RecordingDecisionMemoryPort()
    app = create_app(Settings(), decision_memory_port=decision_memory)
    primary = _result()

    async with app.router.lifespan_context(app):
        caller_bus = _caller_bus(app)
        request = AgentOsPeerReviewRequestPayload(
            primary_result=primary,
            reviewer_category="architect",
            reviewer_result=None,
            reviewer_available=False,
            requesting_engine="test-caller-engine",
            correlation_id=uuid4(),
        )
        reply_envelope = await caller_bus.request(
            "agent_os.supervisor.peer_review.request",
            request,
            source_engine="test-caller-engine",
        )
        result = AgentOsPeerReviewReplyPayload.model_validate(reply_envelope.payload)

    assert result.peer_validation == "timed_out"
    assert len(decision_memory.calls) == 1

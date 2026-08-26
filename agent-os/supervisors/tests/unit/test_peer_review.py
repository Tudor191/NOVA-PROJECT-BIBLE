"""`domain/peer_review.py` -- doc 12 §9's peer-review round; TDD 3E §12's
timeout behavior."""

from __future__ import annotations

from uuid import uuid4

from nova_agent_os_supervisors.domain.peer_review import (
    classify_reviewer_result,
    run_peer_review_round,
)
from nova_contracts import AgentMessage, AgentMessageType, AgentResult

from tests.fakes.instance_port import FakeAgentInstancePort


def _primary_result(**overrides: object) -> AgentResult:
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


async def test_reviewer_approval_sends_peer_review_request_and_returns_approved() -> None:
    primary = _primary_result()
    reviewer_id = uuid4()
    reviewer_result = _primary_result(status="success", agent_instance_id=reviewer_id)
    reply = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_RESULT,
        from_instance_id=reviewer_id,
        to_instance_id=uuid4(),
        payload=reviewer_result.model_dump(mode="json"),
        correlation_id=primary.correlation_id,
    )
    port = FakeAgentInstancePort(reply=reply)

    outcome = await run_peer_review_round(
        primary, reviewer_instance_id=reviewer_id, instance_port=port
    )

    assert outcome.peer_validation == "approved"
    assert outcome.reviewer_result == reviewer_result
    assert len(port.delivered) == 1
    assert port.delivered[0].message_type is AgentMessageType.PEER_REVIEW_REQUEST
    assert port.delivered[0].to_instance_id == reviewer_id


async def test_reviewer_rejection_returns_rejected() -> None:
    primary = _primary_result()
    reviewer_id = uuid4()
    reviewer_result = _primary_result(status="failure", agent_instance_id=reviewer_id)
    reply = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_RESULT,
        from_instance_id=reviewer_id,
        to_instance_id=uuid4(),
        payload=reviewer_result.model_dump(mode="json"),
        correlation_id=primary.correlation_id,
    )
    port = FakeAgentInstancePort(reply=reply)

    outcome = await run_peer_review_round(
        primary, reviewer_instance_id=reviewer_id, instance_port=port
    )

    assert outcome.peer_validation == "rejected"


async def test_reviewer_timeout_proceeds_with_the_primary_result_flagged_timed_out() -> None:
    primary = _primary_result()
    port = FakeAgentInstancePort(raise_timeout=True)

    outcome = await run_peer_review_round(
        primary, reviewer_instance_id=uuid4(), instance_port=port
    )

    assert outcome.peer_validation == "timed_out"
    assert outcome.reviewer_result is None
    assert outcome.primary_result == primary


async def test_no_reply_is_treated_the_same_as_a_timeout() -> None:
    primary = _primary_result()
    port = FakeAgentInstancePort(reply=None)

    outcome = await run_peer_review_round(
        primary, reviewer_instance_id=uuid4(), instance_port=port
    )

    assert outcome.peer_validation == "timed_out"


def test_classify_reviewer_result_none_is_timed_out() -> None:
    assert classify_reviewer_result(None) == "timed_out"


def test_classify_reviewer_result_success_is_approved() -> None:
    assert classify_reviewer_result(_primary_result(status="success")) == "approved"


def test_classify_reviewer_result_needs_revision_is_rejected() -> None:
    assert classify_reviewer_result(_primary_result(status="needs_revision")) == "rejected"

"""`domain/conflict.py` -- doc 12 §9's two-level conflict resolution."""

from __future__ import annotations

from uuid import uuid4

from nova_agent_os_supervisors.domain.conflict import resolve_conflict
from nova_agent_os_supervisors.domain.ports import ReasoningOutcome
from nova_contracts import AgentResult

from tests.fakes.reasoning_port import FakeDecisionMemoryPort, FakeReasoningPort


def _result(**overrides: object) -> AgentResult:
    defaults: dict[str, object] = {
        "agent_instance_id": uuid4(),
        "task_node_id": uuid4(),
        "status": "success",
        "output": {"summary": "ok"},
        "confidence": 0.9,
        "self_validation_passed": True,
        "correlation_id": uuid4(),
    }
    defaults.update(overrides)
    return AgentResult(**defaults)


async def test_disagreeing_status_resolves_locally_trusting_the_failure() -> None:
    coding_result = _result(status="success")
    qa_result = _result(status="failure")
    reasoning_port = FakeReasoningPort(
        outcome=ReasoningOutcome(
            outcome="succeeded", chosen_description=None, confidence_score=None
        )
    )
    decision_memory = FakeDecisionMemoryPort()

    record = await resolve_conflict(
        description="coding-agent vs qa-agent",
        result_a=coding_result,
        result_b=qa_result,
        reasoning_port=reasoning_port,
        decision_memory_port=decision_memory,
        user_id=uuid4(),
        correlation_id=uuid4(),
    )

    assert record.resolution == "supervisor_resolved"
    assert str(qa_result.agent_instance_id) in record.outcome
    assert reasoning_port.calls == []
    assert len(decision_memory.records) == 1


async def test_agreeing_status_with_different_output_escalates_to_reasoning() -> None:
    result_a = _result(status="success", output={"summary": "approach A"})
    result_b = _result(status="success", output={"summary": "approach B"})
    reasoning_port = FakeReasoningPort(
        outcome=ReasoningOutcome(
            outcome="succeeded", chosen_description="approach A is correct", confidence_score=0.8
        )
    )
    decision_memory = FakeDecisionMemoryPort()

    record = await resolve_conflict(
        description="two architects disagree",
        result_a=result_a,
        result_b=result_b,
        reasoning_port=reasoning_port,
        decision_memory_port=decision_memory,
        user_id=uuid4(),
        correlation_id=uuid4(),
    )

    assert record.resolution == "escalated_to_reasoning"
    assert len(reasoning_port.calls) == 1
    assert "approach A is correct" in record.outcome
    assert len(decision_memory.records) == 1


async def test_both_failing_with_different_output_also_escalates() -> None:
    result_a = _result(status="failure", output={"error": "timeout"})
    result_b = _result(status="needs_revision", output={"error": "syntax"})
    reasoning_port = FakeReasoningPort(
        outcome=ReasoningOutcome(
            outcome="succeeded", chosen_description=None, confidence_score=None
        )
    )
    decision_memory = FakeDecisionMemoryPort()

    record = await resolve_conflict(
        description="both failing",
        result_a=result_a,
        result_b=result_b,
        reasoning_port=reasoning_port,
        decision_memory_port=decision_memory,
        user_id=uuid4(),
        correlation_id=uuid4(),
    )

    assert record.resolution == "escalated_to_reasoning"

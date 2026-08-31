"""`domain/decomposition.py` unit tests -- fake-backed (Part 16), never a
real model. Covers the full happy path (structured tool-call -> validated
`TaskGraph`) and every defined failure mode (Part 14): model
timeout/error, no structured output, and every malformed/invalid shape
`_build_nodes` and PR #2's structural checks reject.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_contracts import GenerateReplyPayload, ToolCallPayload
from nova_planning_engine.domain.decomposition import DecompositionError, decompose, decompose_node
from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskNode

from tests.fakes.ports import FakeModelOrchestrationPort

_TOOL_NAME = "propose_task_graph"


def _reply(tasks: object, *, finish_reason: str = "tool_calls") -> GenerateReplyPayload:
    tool_calls = (
        [ToolCallPayload(id="call_0", tool_name=_TOOL_NAME, arguments={"tasks": tasks})]
        if finish_reason == "tool_calls"
        else []
    )
    return GenerateReplyPayload(
        text="",
        tool_calls=tool_calls,
        input_tokens=10,
        output_tokens=10,
        finish_reason=finish_reason,
        structural_confidence=0.9,
        model_id=uuid4(),
        provider="fake",
    )


async def test_decompose_builds_valid_task_graph_from_structured_reply() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "Set up the project skeleton",
                    "depends_on": [],
                    "assigned_agent_category": "coding-agent",
                    "effort_hours": 2.0,
                    "confidence": 0.8,
                    "risk": "low",
                },
                {
                    "local_id": "b",
                    "objective": "Implement the feature",
                    "depends_on": ["a"],
                    "assigned_agent_category": None,
                    "effort_hours": 5.0,
                    "confidence": 0.6,
                    "risk": "moderate",
                },
            ]
        )
    )

    graph = await decompose(
        root_objective="Ship the feature",
        chosen_description="Build it incrementally",
        model_port=port,
        requesting_engine="planning-engine",
        correlation_id=uuid4(),
    )

    assert graph.root_objective == "Ship the feature"
    assert len(graph.nodes) == 2
    by_objective = {n.objective: n for n in graph.nodes}
    node_a = by_objective["Set up the project skeleton"]
    node_b = by_objective["Implement the feature"]
    assert node_b.depends_on == [node_a.id]
    assert node_a.assigned_agent_category == "coding-agent"
    assert node_b.assigned_agent_category is None
    assert node_a.risk.value == "low"
    assert node_b.estimated_effort.effort_hours == 5.0
    # Critical path: both nodes, in dependency order (a before b).
    assert graph.critical_path == [node_a.id, node_b.id]


async def test_decompose_propagates_objective_and_chosen_description_into_context() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "x",
                    "depends_on": [],
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                }
            ]
        )
    )

    await decompose(
        root_objective="Real objective text",
        chosen_description="Real chosen description",
        model_port=port,
        requesting_engine="planning-engine",
        correlation_id=uuid4(),
    )

    sent = port.requests[0]
    texts = [c.text for c in sent.context]
    assert "Real objective text" in texts
    assert "Real chosen description" in texts
    assert sent.tools[0].name == _TOOL_NAME


async def test_decompose_omits_chosen_description_component_when_none() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "x",
                    "depends_on": [],
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                }
            ]
        )
    )

    await decompose(
        root_objective="Objective only",
        chosen_description=None,
        model_port=port,
        requesting_engine="planning-engine",
        correlation_id=uuid4(),
    )

    sent = port.requests[0]
    sources = [c.source for c in sent.context]
    assert "chosen_approach" not in sources


async def test_decompose_raises_on_model_timeout() -> None:
    class _TimeoutPort:
        async def generate(self, request: object) -> GenerateReplyPayload:
            raise TimeoutError("boom")

    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=_TimeoutPort(),
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "model_timeout"


async def test_decompose_raises_on_model_error_finish_reason() -> None:
    port = FakeModelOrchestrationPort(
        reply=GenerateReplyPayload(
            text="",
            input_tokens=0,
            output_tokens=0,
            finish_reason="error",
            structural_confidence=0.0,
            model_id=uuid4(),
            provider="fake",
            error="provider unavailable",
        )
    )
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "model_error"


async def test_decompose_raises_when_no_tool_call_returned() -> None:
    port = FakeModelOrchestrationPort(reply=_reply([], finish_reason="stop"))
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "no_structured_output"


async def test_decompose_raises_on_empty_task_list() -> None:
    port = FakeModelOrchestrationPort(reply=_reply([]))
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "empty_task_list"


async def test_decompose_raises_on_malformed_task_entry() -> None:
    port = FakeModelOrchestrationPort(reply=_reply(["not-an-object"]))
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "malformed_task"


async def test_decompose_raises_on_missing_local_id() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "objective": "x",
                    "depends_on": [],
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                }
            ]
        )
    )
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "malformed_task"


async def test_decompose_raises_on_malformed_depends_on() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "x",
                    "depends_on": "not-a-list",
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                }
            ]
        )
    )
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "malformed_task"


async def test_decompose_raises_on_duplicate_local_id() -> None:
    task = {
        "local_id": "a",
        "objective": "x",
        "depends_on": [],
        "effort_hours": 1.0,
        "confidence": 0.5,
        "risk": "low",
    }
    port = FakeModelOrchestrationPort(reply=_reply([task, dict(task)]))
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "duplicate_local_id"


async def test_decompose_raises_on_unknown_dependency_reference() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "x",
                    "depends_on": ["does-not-exist"],
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                }
            ]
        )
    )
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "unknown_dependency_reference"


@pytest.mark.parametrize(
    "field,value",
    [
        ("effort_hours", -1.0),
        ("confidence", 1.5),
        ("risk", "not-a-real-risk-level"),
    ],
)
async def test_decompose_raises_on_malformed_task_fields(field: str, value: object) -> None:
    task = {
        "local_id": "a",
        "objective": "x",
        "depends_on": [],
        "effort_hours": 1.0,
        "confidence": 0.5,
        "risk": "low",
    }
    task[field] = value
    port = FakeModelOrchestrationPort(reply=_reply([task]))
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "malformed_task_fields"


async def test_decompose_raises_on_cycle() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "x",
                    "depends_on": ["b"],
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                },
                {
                    "local_id": "b",
                    "objective": "y",
                    "depends_on": ["a"],
                    "effort_hours": 1.0,
                    "confidence": 0.5,
                    "risk": "low",
                },
            ]
        )
    )
    with pytest.raises(DecompositionError) as exc_info:
        await decompose(
            root_objective="x",
            chosen_description=None,
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "cycle"


def _target_node() -> TaskNode:
    return TaskNode(
        objective="Implement the feature",
        depends_on=[],
        estimated_effort=Estimate(effort_hours=5.0, confidence=0.6),
        risk=RiskLevel.MODERATE,
    )


async def test_decompose_node_returns_empty_list_when_model_proposes_no_further_breakdown() -> (
    None
):
    """TDD 3B §8's "already minimal" case: the model's own reply resolves to
    exactly one task (unmodified from `node`'s own objective) -- distinct
    from a genuine breakdown into multiple subtasks."""
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "Implement the feature",
                    "depends_on": [],
                    "effort_hours": 5.0,
                    "confidence": 0.6,
                    "risk": "moderate",
                }
            ]
        )
    )
    new_nodes = await decompose_node(
        node=_target_node(),
        model_port=port,
        requesting_engine="planning-engine",
        correlation_id=uuid4(),
    )
    assert new_nodes == []


async def test_decompose_node_returns_the_proposed_subtasks_on_a_genuine_breakdown() -> None:
    port = FakeModelOrchestrationPort(
        reply=_reply(
            [
                {
                    "local_id": "a",
                    "objective": "Design the schema",
                    "depends_on": [],
                    "effort_hours": 1.0,
                    "confidence": 0.7,
                    "risk": "low",
                },
                {
                    "local_id": "b",
                    "objective": "Implement the migration",
                    "depends_on": ["a"],
                    "effort_hours": 2.0,
                    "confidence": 0.6,
                    "risk": "moderate",
                },
            ]
        )
    )
    new_nodes = await decompose_node(
        node=_target_node(),
        model_port=port,
        requesting_engine="planning-engine",
        correlation_id=uuid4(),
    )
    assert {n.objective for n in new_nodes} == {"Design the schema", "Implement the migration"}


async def test_decompose_node_propagates_decomposition_error() -> None:
    """`decompose_node` reuses `decompose()`'s pipeline unchanged -- a
    defined failure (e.g. `no_structured_output`) propagates to the caller
    (`events/decompose_handler.py`) rather than being swallowed here."""
    port = FakeModelOrchestrationPort(reply=_reply([], finish_reason="stop"))
    with pytest.raises(DecompositionError) as exc_info:
        await decompose_node(
            node=_target_node(),
            model_port=port,
            requesting_engine="planning-engine",
            correlation_id=uuid4(),
        )
    assert exc_info.value.reason == "no_structured_output"

from uuid import uuid4

from nova_contracts import (
    AgentContext,
    AgentHealth,
    AgentMetrics,
    AgentResult,
    CapabilityHandle,
    KnowledgeReference,
    MemoryReference,
    PermissionSet,
    ResourceUsage,
    RiskLevel,
    TaskNodeSnapshot,
    ValidationOutcome,
    WorldModelSnapshot,
)


def _task_node() -> TaskNodeSnapshot:
    return TaskNodeSnapshot(
        id=uuid4(),
        objective="add a health-check endpoint",
        effort_hours=2.0,
        confidence=0.8,
        risk=RiskLevel.LOW,
        status="ready",
    )


def test_agent_context_constructs_from_already_existing_nova_contracts_types() -> None:
    context = AgentContext(
        task=_task_node(),
        world_model_slice=WorldModelSnapshot(user_id=uuid4(), objective="ship the feature"),
        relevant_memory=[MemoryReference(memory_id=uuid4(), summary="prior similar task")],
        relevant_knowledge=[KnowledgeReference(node_id="kn-1", summary="relevant doc")],
        granted_permissions=PermissionSet(granted=["filesystem:write:project-scope"]),
        granted_capabilities=[
            CapabilityHandle(capability_id=uuid4(), name="git", execution_adapter="git")
        ],
        correlation_id=uuid4(),
    )
    round_tripped = AgentContext.model_validate(context.model_dump(mode="json"))
    assert round_tripped == context


def test_agent_context_defaults_empty_memory_and_knowledge_and_capabilities() -> None:
    context = AgentContext(
        task=_task_node(),
        world_model_slice=WorldModelSnapshot(user_id=uuid4()),
        granted_permissions=PermissionSet(),
        correlation_id=uuid4(),
    )
    assert context.relevant_memory == []
    assert context.relevant_knowledge == []
    assert context.granted_capabilities == []


def test_agent_health_matches_doc_12_4_field_set() -> None:
    health = AgentHealth(
        status="healthy",
        latency_ms=42.0,
        error_rate=0.0,
        resource_usage=ResourceUsage(cpu_percent=12.5, memory_mb=256.0),
    )
    assert health.status == "healthy"
    assert health.resource_usage.cpu_percent == 12.5


def test_agent_metrics_matches_doc_12_4_field_set() -> None:
    metrics = AgentMetrics(
        tasks_completed=10,
        tasks_failed=1,
        average_duration_ms=1500.0,
        average_confidence=0.87,
        resource_efficiency=0.9,
    )
    assert metrics.tasks_completed == 10


def test_agent_result_round_trips() -> None:
    result = AgentResult(
        agent_instance_id=uuid4(),
        task_node_id=uuid4(),
        status="success",
        output={"summary": "endpoint added"},
        confidence=0.9,
        self_validation_passed=True,
        correlation_id=uuid4(),
    )
    round_tripped = AgentResult.model_validate(result.model_dump(mode="json"))
    assert round_tripped == result


def test_validation_outcome_maps_lifecycle_transitions() -> None:
    sufficient = ValidationOutcome(passed=True, requires_peer_review=False)
    assert sufficient.requires_peer_review is False

    needs_review = ValidationOutcome(
        passed=True, requires_peer_review=True, reason="risk classification requires review"
    )
    assert needs_review.requires_peer_review is True

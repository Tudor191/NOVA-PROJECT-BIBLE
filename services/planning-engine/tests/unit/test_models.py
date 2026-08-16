from uuid import uuid4

import pytest
from nova_contracts import RiskLevel
from nova_planning_engine.domain.models import Estimate, TaskGraph, TaskNode
from pydantic import ValidationError


def _estimate(**overrides: object) -> Estimate:
    defaults: dict[str, object] = {"effort_hours": 4.0, "confidence": 0.7}
    defaults.update(overrides)
    return Estimate(**defaults)  # type: ignore[arg-type]


def test_task_node_constructs_with_required_fields_only() -> None:
    node = TaskNode(
        objective="stand up the database schema",
        estimated_effort=_estimate(),
        risk=RiskLevel.LOW,
    )
    assert node.objective == "stand up the database schema"
    assert node.depends_on == []
    assert node.assigned_agent_category is None
    assert node.status == "pending"
    assert node.id is not None


def test_task_node_requires_objective() -> None:
    with pytest.raises(ValidationError):
        TaskNode(estimated_effort=_estimate(), risk=RiskLevel.LOW)  # type: ignore[call-arg]


def test_task_node_requires_estimated_effort() -> None:
    with pytest.raises(ValidationError):
        TaskNode(objective="x", risk=RiskLevel.LOW)  # type: ignore[call-arg]


def test_task_node_requires_risk() -> None:
    with pytest.raises(ValidationError):
        TaskNode(objective="x", estimated_effort=_estimate())  # type: ignore[call-arg]


def test_task_node_accepts_optional_fields_when_supplied() -> None:
    dep_id = uuid4()
    node = TaskNode(
        objective="implement the API layer",
        depends_on=[dep_id],
        assigned_agent_category="coding-agent",
        estimated_effort=_estimate(effort_hours=8.0),
        risk=RiskLevel.MODERATE,
        status="ready",
    )
    assert node.depends_on == [dep_id]
    assert node.assigned_agent_category == "coding-agent"
    assert node.status == "ready"


def test_task_node_status_rejects_values_outside_doc06_schema() -> None:
    with pytest.raises(ValidationError):
        TaskNode(
            objective="x",
            estimated_effort=_estimate(),
            risk=RiskLevel.LOW,
            status="in_progress",  # type: ignore[arg-type]
        )


def test_task_node_wbs_fields_map_bible_part_9_directly() -> None:
    """Fork 3B-2: `estimated_effort`/`depends_on`/`assigned_agent_category`
    are the three of Bible Part 9's seven WBS fields doc06 §3 maps
    directly onto `TaskNode` (plus `risk`, from Part 9's own "Risk
    Analysis" section) -- confirmed present."""
    fields = TaskNode.model_fields
    assert "estimated_effort" in fields
    assert "depends_on" in fields
    assert "assigned_agent_category" in fields
    assert "risk" in fields


def test_task_node_omits_the_four_undecided_wbs_fields() -> None:
    """Fork 3B-2 (approved): `completion_criteria`/`deliverables`/
    `required_knowledge`/`required_tools` are Bible-Part-9-only fields with
    no Phase 3 consumer (confirmed against TDD 3C/3D/3E) -- deliberately
    absent, not silently dropped. A regression test, not just a docstring
    claim: if a future change adds one of these back, this test forces an
    explicit decision to update it rather than a silent contract change."""
    fields = TaskNode.model_fields
    for absent_field in (
        "completion_criteria",
        "deliverables",
        "required_knowledge",
        "required_tools",
    ):
        assert absent_field not in fields


def test_estimate_requires_positive_effort_hours() -> None:
    with pytest.raises(ValidationError):
        _estimate(effort_hours=0.0)
    with pytest.raises(ValidationError):
        _estimate(effort_hours=-1.0)


def test_estimate_confidence_is_bounded_zero_to_one() -> None:
    with pytest.raises(ValidationError):
        _estimate(confidence=-0.1)
    with pytest.raises(ValidationError):
        _estimate(confidence=1.1)
    assert _estimate(confidence=0.0).confidence == 0.0
    assert _estimate(confidence=1.0).confidence == 1.0


def test_risk_level_is_bible_part_14s_five_tier_scale() -> None:
    """Fork 3B-1 (approved): confirms the exact five values, in Bible Part
    14's own order -- reused verbatim, not a competing scale."""
    assert list(RiskLevel) == [
        RiskLevel.NEGLIGIBLE,
        RiskLevel.LOW,
        RiskLevel.MODERATE,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]


def test_risk_level_is_importable_from_nova_contracts_directly() -> None:
    """Compatibility with the expected Phase 3D consumption model: TDD 3D's
    own `ActionObject.risk: RiskLevel` must be constructible from
    `nova_contracts.RiskLevel` alone, without importing `nova_planning_engine`
    at all (ADR-004 forbids direct cross-engine imports) -- this test
    exercises exactly that shape, standing in for action-engine's own future
    usage."""
    from nova_contracts import RiskLevel as ImportedElsewhere

    node = TaskNode(
        objective="x", estimated_effort=_estimate(), risk=ImportedElsewhere.CRITICAL
    )
    assert node.risk is RiskLevel.CRITICAL


def test_task_graph_constructs_with_required_fields_only() -> None:
    graph = TaskGraph(root_objective="build an online store")
    assert graph.root_objective == "build an online store"
    assert graph.nodes == []
    assert graph.critical_path == []
    assert graph.id is not None


def test_task_graph_requires_root_objective() -> None:
    with pytest.raises(ValidationError):
        TaskGraph()  # type: ignore[call-arg]


def test_task_graph_preserves_node_insertion_order() -> None:
    """Deterministic node ordering: `nodes` is a plain list, not a set or
    dict keyed by ID -- insertion order survives construction unchanged."""
    first = TaskNode(objective="a", estimated_effort=_estimate(), risk=RiskLevel.LOW)
    second = TaskNode(objective="b", estimated_effort=_estimate(), risk=RiskLevel.LOW)
    third = TaskNode(objective="c", estimated_effort=_estimate(), risk=RiskLevel.LOW)
    graph = TaskGraph(root_objective="x", nodes=[first, second, third])
    assert [n.id for n in graph.nodes] == [first.id, second.id, third.id]


def test_task_graph_round_trips_through_json_serialization() -> None:
    """Serialization boundary this PR's architecture actually requires:
    the persistence layer (a later PR) stores `TaskGraph`/`TaskNode` as
    JSONB, per TDD 3B §4's already-established convention -- proving a
    clean `model_dump(mode="json")` / `model_validate()` round trip now is
    the structural precondition that later work depends on, without
    implementing the persistence layer itself here."""
    dep = TaskNode(objective="schema", estimated_effort=_estimate(), risk=RiskLevel.LOW)
    dependent = TaskNode(
        objective="api",
        depends_on=[dep.id],
        estimated_effort=_estimate(effort_hours=6.0),
        risk=RiskLevel.MODERATE,
    )
    graph = TaskGraph(
        root_objective="build the service",
        nodes=[dep, dependent],
        critical_path=[dep.id, dependent.id],
    )

    dumped = graph.model_dump(mode="json")
    restored = TaskGraph.model_validate(dumped)

    assert restored == graph

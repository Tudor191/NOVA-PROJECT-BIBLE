from uuid import uuid4

from nova_contracts import (
    PlanningDecomposeReplyPayload,
    PlanningDecomposeRequestPayload,
    PlanningTaskGraphCreatedPayload,
    RiskLevel,
    TaskGraphSnapshot,
    TaskNodeSnapshot,
    known_subjects,
)


def test_risk_level_is_importable_from_the_top_level_package() -> None:
    assert RiskLevel.LOW.value == "low"


def test_risk_level_matches_bible_part_14s_five_tier_scale_verbatim() -> None:
    assert [member.value for member in RiskLevel] == [
        "negligible",
        "low",
        "moderate",
        "high",
        "critical",
    ]


def test_all_planning_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "planning.task_graph.created",
        "planning.decompose.request",
        "planning.decompose.reply",
    ):
        assert subject in subjects


def _node(**overrides: object) -> TaskNodeSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "objective": "write the failing test first",
        "effort_hours": 2.0,
        "confidence": 0.8,
        "risk": RiskLevel.LOW,
        "status": "pending",
    }
    defaults.update(overrides)
    return TaskNodeSnapshot(**defaults)  # type: ignore[arg-type]


def test_planning_task_graph_created_round_trips_a_multi_node_snapshot() -> None:
    root = _node()
    dependent = _node(depends_on=[root.id])
    graph = TaskGraphSnapshot(
        id=uuid4(),
        root_objective="ship the feature",
        nodes=[root, dependent],
        critical_path=[root.id, dependent.id],
    )
    payload = PlanningTaskGraphCreatedPayload(graph=graph, correlation_id=uuid4())

    round_tripped = PlanningTaskGraphCreatedPayload.model_validate(
        payload.model_dump(mode="json")
    )
    assert round_tripped == payload
    assert round_tripped.schema_version == 1
    assert round_tripped.graph.approved_at is None


def test_planning_decompose_request_reply_round_trip() -> None:
    request = PlanningDecomposeRequestPayload(
        task_node_id=uuid4(), requesting_engine="agent-os-kernel", correlation_id=uuid4()
    )
    assert (
        PlanningDecomposeRequestPayload.model_validate(request.model_dump(mode="json"))
        == request
    )

    already_minimal_reply = PlanningDecomposeReplyPayload(already_minimal=True)
    assert already_minimal_reply.new_nodes == []

    decomposed_reply = PlanningDecomposeReplyPayload(already_minimal=False, new_nodes=[_node()])
    round_tripped_reply = PlanningDecomposeReplyPayload.model_validate(
        decomposed_reply.model_dump(mode="json")
    )
    assert round_tripped_reply == decomposed_reply

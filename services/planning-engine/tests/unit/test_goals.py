"""Unit tests for `domain/goals.py` -- TDD 3E §8's `goal_tier`/`priority`
derivations plus the `is_active` heuristic proposed alongside them (module
docstring). Pure functions over `TaskGraph`, no repository or Event Bus
involved."""

from __future__ import annotations

from nova_planning_engine.domain.goals import (
    critical_path_effort_sum,
    goal_tier_for,
    is_active,
    priority_for,
    rank_active_graphs,
    to_goal_snapshot,
)
from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskGraph, TaskNode


def _node(*, effort_hours: float = 1.0, status: str = "ready") -> TaskNode:
    return TaskNode(
        objective="do the thing",
        depends_on=[],
        estimated_effort=Estimate(effort_hours=effort_hours, confidence=0.7),
        risk=RiskLevel.LOW,
        status=status,  # type: ignore[arg-type]
    )


def test_is_active_true_when_any_node_is_not_terminal() -> None:
    node = _node(status="running")
    graph = TaskGraph(root_objective="ship it", nodes=[node], critical_path=[node.id])
    assert is_active(graph) is True


def test_is_active_false_when_every_node_is_terminal() -> None:
    n1 = _node(status="completed")
    n2 = _node(status="failed")
    graph = TaskGraph(root_objective="ship it", nodes=[n1, n2], critical_path=[n1.id, n2.id])
    assert is_active(graph) is False


def test_is_active_false_for_an_empty_graph() -> None:
    graph = TaskGraph(root_objective="ship it", nodes=[], critical_path=[])
    assert is_active(graph) is False


def test_goal_tier_established_for_multi_node_graphs() -> None:
    n1, n2 = _node(), _node()
    graph = TaskGraph(root_objective="ship it", nodes=[n1, n2], critical_path=[n1.id, n2.id])
    assert goal_tier_for(graph) == "established"


def test_goal_tier_ad_hoc_for_single_node_graphs() -> None:
    node = _node()
    graph = TaskGraph(root_objective="ship it", nodes=[node], critical_path=[node.id])
    assert goal_tier_for(graph) == "ad_hoc"


def test_critical_path_effort_sum_only_counts_nodes_on_the_path() -> None:
    on_path = _node(effort_hours=3.0)
    off_path = _node(effort_hours=100.0)
    graph = TaskGraph(
        root_objective="ship it", nodes=[on_path, off_path], critical_path=[on_path.id]
    )
    assert critical_path_effort_sum(graph) == 3.0


def test_rank_active_graphs_orders_descending_by_critical_path_effort() -> None:
    low = _node(effort_hours=1.0)
    high = _node(effort_hours=5.0)
    graph_low = TaskGraph(root_objective="low", nodes=[low], critical_path=[low.id])
    graph_high = TaskGraph(root_objective="high", nodes=[high], critical_path=[high.id])
    ranked = rank_active_graphs([graph_low, graph_high])
    assert [g.id for g in ranked] == [graph_high.id, graph_low.id]


def test_rank_active_graphs_tie_breaks_by_task_graph_id() -> None:
    n1, n2 = _node(effort_hours=2.0), _node(effort_hours=2.0)
    g1 = TaskGraph(root_objective="a", nodes=[n1], critical_path=[n1.id])
    g2 = TaskGraph(root_objective="b", nodes=[n2], critical_path=[n2.id])
    ranked = rank_active_graphs([g2, g1])
    expected_order = sorted([g1, g2], key=lambda g: g.id)
    assert [g.id for g in ranked] == [g.id for g in expected_order]


def test_priority_for_single_graph_is_maximal() -> None:
    assert priority_for(0, 1) == 1.0


def test_priority_for_ranks_descending_across_multiple_graphs() -> None:
    assert priority_for(0, 3) == 1.0
    assert priority_for(1, 3) == 0.5
    assert priority_for(2, 3) == 0.0


def test_to_goal_snapshot_combines_all_derivations() -> None:
    node = _node(effort_hours=4.0)
    graph = TaskGraph(root_objective="Ship rate limiting", nodes=[node], critical_path=[node.id])
    snapshot = to_goal_snapshot(graph, rank_index=0, total=2)
    assert snapshot.id == graph.id
    assert snapshot.description == "Ship rate limiting"
    assert snapshot.goal_tier == "ad_hoc"
    assert snapshot.priority == 1.0

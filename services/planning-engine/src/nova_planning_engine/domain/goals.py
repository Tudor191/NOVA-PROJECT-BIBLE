"""`planning.goals.current.request`'s own derivation logic (TDD 3E §8,
Fork 3E-3 resolved 2026-08-19) -- pure functions over `TaskGraph`, the same
"domain functions operate on and return plain models" shape `task_graph.py`
and `decision_matrix.py` already establish, kept separate from
`events/goals_handler.py` so the derivation itself is unit-testable without
a request/reply round trip.

Three derivations, all approved as proposed in TDD 3E §8:
- `goal_tier`: `"established"` iff `len(graph.nodes) > 1`, else `"ad_hoc"`.
- `priority`: `1.0 - (rank_index / max(1, len(active_graphs) - 1))`, ranking
  a user's active `TaskGraph`s descending by critical-path effort sum,
  tie-broken by `TaskGraph.id`.
- `is_active`: **not** one of TDD 3E §8's own named derivations -- no
  document defines what "active" means for a `TaskGraph` (it carries no
  lifecycle/status field of its own, only `approved_at` and each node's own
  `TaskNodeStatus`). Proposed here, disclosed rather than silently assumed:
  a graph is active iff it has at least one node and at least one of those
  nodes is not yet in a terminal state (`completed`/`failed`) -- finished
  work is not a "current goal." Flagged for the same explicit-approval
  treatment already given `goal_tier`/`priority` themselves.
"""

from __future__ import annotations

from typing import Literal

from nova_contracts import GoalSnapshot

from nova_planning_engine.domain.models import TaskGraph

__all__ = [
    "critical_path_effort_sum",
    "goal_tier_for",
    "is_active",
    "priority_for",
    "rank_active_graphs",
    "to_goal_snapshot",
]

_TERMINAL_STATUSES = frozenset({"completed", "failed"})


def is_active(graph: TaskGraph) -> bool:
    """Proposed heuristic (see module docstring) -- flagged for approval,
    not extracted from any document."""
    return any(node.status not in _TERMINAL_STATUSES for node in graph.nodes)


def goal_tier_for(graph: TaskGraph) -> Literal["ad_hoc", "established"]:
    """TDD 3E §8, Fork 3E-3 (approved 2026-08-19): `"established"` iff the
    graph came from a multi-node decomposition, else `"ad_hoc"`. Derived at
    read time, never persisted."""
    return "established" if len(graph.nodes) > 1 else "ad_hoc"


def critical_path_effort_sum(graph: TaskGraph) -> float:
    """Sum of `estimated_effort.effort_hours` for every node on the
    graph's own `critical_path` -- the ranking key TDD 3E §8's `priority`
    formula ranks by."""
    on_path = set(graph.critical_path)
    return sum(node.estimated_effort.effort_hours for node in graph.nodes if node.id in on_path)


def rank_active_graphs(graphs: list[TaskGraph]) -> list[TaskGraph]:
    """Descending by `critical_path_effort_sum`, tie-broken ascending by
    `TaskGraph.id` (TDD 3E §8's own exact tie-break rule)."""
    return sorted(graphs, key=lambda g: (-critical_path_effort_sum(g), g.id))


def priority_for(rank_index: int, total: int) -> float:
    """TDD 3E §8's own exact formula: `1.0 - (rank_index / max(1, total - 1))`."""
    return 1.0 - (rank_index / max(1, total - 1))


def to_goal_snapshot(graph: TaskGraph, *, rank_index: int, total: int) -> GoalSnapshot:
    return GoalSnapshot(
        id=graph.id,
        description=graph.root_objective,
        priority=priority_for(rank_index, total),
        goal_tier=goal_tier_for(graph),
    )

"""Task Graph structural invariants and critical-path computation (Bible
Part 9 "Critical Path Analysis"), kept separate from `domain/models.py`'s
plain data classes -- pure functions over `TaskNode`, the same "domain
functions operate on and return plain models" shape every other domain
module in this codebase already uses (e.g. `reasoning-engine`'s
`decision_matrix.py`, `confidence.py`), rather than Pydantic
`@model_validator`-based auto-validation/computation, for which no
precedent exists anywhere in this codebase's domain layers today.

Deliberately excludes: deriving `TaskNode`s from a `reasoning.process.completed`
event (decomposition orchestration -- a later, event-consumption PR's job)
and mutating a persisted graph in place (the persistence-layer PR's job).
This module is only concerned with the graph as a structure: is it valid,
what is its critical path, and -- since TDD 3E §4 defines `"ready"` purely
as a property *of the graph* ("for each `TaskNode` with `status="ready"`
(all `depends_on` complete)") -- which of its nodes that definition admits
right now (`admit`, `promotable_ids`). Those two are structural queries in
exactly the same sense `compute_critical_path` is; they decide nothing
about *when* a transition happens (that is
`domain/task_completion.py`'s job) and touch no persistence.

Known, accepted limitation: `find_cycle`/`compute_critical_path` use plain
Python recursion (one stack frame per DFS/longest-path level), matching
`reasoning-engine`'s own Phase 3A Multi-step recursion (bounded depth, not
converted to an iterative form) -- fine at planning-engine's realistic
scale (dozens to low hundreds of `TaskNode`s per graph), not proven safe
against an adversarially deep chain. Revisit if a real graph ever
approaches Python's recursion limit.
"""

from __future__ import annotations

from uuid import UUID

from nova_planning_engine.domain.models import TaskNode

__all__ = [
    "admit",
    "compute_critical_path",
    "dependencies_satisfied",
    "find_cycle",
    "find_dangling_dependencies",
    "find_duplicate_ids",
    "has_cycle",
    "promotable_ids",
]


def dependencies_satisfied(node: TaskNode, *, by_id: dict[UUID, TaskNode]) -> bool:
    """TDD 3E §4:140's own parenthetical definition of `"ready"` -- "all
    `depends_on` complete" -- evaluated literally against `by_id`.

    A dependency id absent from `by_id` counts as **not** satisfied
    (fail-closed): a node whose dependency does not exist can never be
    proven runnable, so it must not be dispatched. In practice this never
    fires -- `compute_critical_path` rejects a dangling `depends_on`
    reference before any graph is persisted (`find_dangling_dependencies`)
    -- but the check is here rather than assumed, so a future caller that
    skips that validation degrades into "never dispatched" rather than
    "dispatched against a phantom dependency"."""
    return all(
        dep_id in by_id and by_id[dep_id].status == "completed" for dep_id in node.depends_on
    )


def admit(nodes: list[TaskNode]) -> list[TaskNode]:
    """Graph admission: returns `nodes` with every `"pending"` node whose
    dependencies are already satisfied re-stamped `"ready"`, every other
    node returned unchanged (identity, not a copy, when nothing changes).

    This is the step whose absence made the real Reasoning -> Planning ->
    Kernel path dispatch nothing at all: `TaskNode.status` defaults to
    `"pending"` (`domain/models.py`), `decompose()` never overrode it, and
    `agent-os/kernel`'s own Scheduler dispatches **only** `"ready"` nodes --
    so a structurally perfect, correctly-categorised Task Graph produced
    zero agent instances. Admission is what makes TDD 3E §4's own
    precondition reachable.

    Deliberately scoped to `"pending"` nodes: a `"running"`, `"completed"`,
    or `"failed"` node is never re-admitted, so calling this on an
    already-live graph (as `append_nodes` does for a mid-flight
    `planning.decompose.request` mutation) can only ever promote the
    genuinely new, dependency-free nodes it just added."""
    by_id = {node.id: node for node in nodes}
    return [
        node.model_copy(update={"status": "ready"})
        if node.status == "pending" and dependencies_satisfied(node, by_id=by_id)
        else node
        for node in nodes
    ]


def promotable_ids(nodes: list[TaskNode]) -> list[UUID]:
    """The ids `admit` would re-stamp `"ready"`, in `nodes` order -- the
    same predicate expressed as ids rather than rebuilt nodes, for the
    caller (`domain/task_completion.py`) that has to describe transitions
    to the repository as `(id, status)` pairs rather than hand it a whole
    node list."""
    by_id = {node.id: node for node in nodes}
    return [
        node.id
        for node in nodes
        if node.status == "pending" and dependencies_satisfied(node, by_id=by_id)
    ]


def find_duplicate_ids(nodes: list[TaskNode]) -> list[UUID]:
    """The subset of `nodes`' own `id`s that appear more than once, in
    first-duplicate-encountered order. Empty list when every `id` is unique.
    Load-bearing for every other function here: `find_cycle`,
    `find_dangling_dependencies`, and `compute_critical_path` all key a
    `dict` by `node.id`, which silently drops all but the last node sharing
    an `id` -- this function is what lets a caller detect that condition
    explicitly instead of it corrupting every other check silently."""
    seen: set[UUID] = set()
    duplicates: list[UUID] = []
    for node in nodes:
        if node.id in seen and node.id not in duplicates:
            duplicates.append(node.id)
        seen.add(node.id)
    return duplicates


def find_cycle(nodes: list[TaskNode]) -> list[UUID] | None:
    """One cycle (node IDs, in cycle order, first entry repeated last) if
    `nodes`' `depends_on` edges contain one, `None` if the graph is a valid
    DAG. Standard three-colour DFS (white/grey/black); deterministic in the
    order it walks `nodes`, so the same node set always reports the same
    cycle, not merely *a* cycle. Ignores dangling references (a `depends_on`
    ID with no matching node) -- `find_dangling_dependencies` reports those
    separately. Assumes `nodes` has no duplicate `id`s -- call
    `find_duplicate_ids` first if that is not already guaranteed; this
    function keys a `dict` by `node.id` and silently drops all but the last
    node sharing one, the same way every other function here does."""
    by_id = {node.id: node for node in nodes}
    white, grey, black = 0, 1, 2
    color: dict[UUID, int] = dict.fromkeys(by_id, white)
    path: list[UUID] = []

    def visit(node_id: UUID) -> list[UUID] | None:
        color[node_id] = grey
        path.append(node_id)
        for dep_id in by_id[node_id].depends_on:
            if dep_id not in by_id:
                continue
            if color[dep_id] == grey:
                return [*path[path.index(dep_id) :], dep_id]
            if color[dep_id] == white:
                found = visit(dep_id)
                if found is not None:
                    return found
        path.pop()
        color[node_id] = black
        return None

    for node in nodes:
        if color[node.id] == white:
            found = visit(node.id)
            if found is not None:
                return found
    return None


def has_cycle(nodes: list[TaskNode]) -> bool:
    return find_cycle(nodes) is not None


def find_dangling_dependencies(nodes: list[TaskNode]) -> dict[UUID, list[UUID]]:
    """Node ID -> the subset of its own `depends_on` entries that do not
    correspond to any other node in `nodes`. Empty dict when every
    dependency resolves within the same graph. Assumes `nodes` has no
    duplicate `id`s -- see `find_cycle`'s identical caveat."""
    by_id = {node.id: node for node in nodes}
    dangling: dict[UUID, list[UUID]] = {}
    for node in nodes:
        missing = [dep_id for dep_id in node.depends_on if dep_id not in by_id]
        if missing:
            dangling[node.id] = missing
    return dangling


def compute_critical_path(nodes: list[TaskNode]) -> list[UUID]:
    """Bible Part 9 "Critical Path Analysis": the longest-by-`effort_hours`
    chain through the DAG `nodes`' `depends_on` edges describe -- standard
    longest-path-in-a-DAG dynamic programming (TDD 3B §12's own framing: "no
    invention needed beyond implementing it"). Raises `ValueError` if `nodes`
    contains a duplicate `id`, a cycle, or a dangling `depends_on` reference
    -- a critical path is undefined for any of the three (duplicate `id`s
    are checked first: every check below keys a `dict` by `node.id` and
    would silently misreport against a graph that has one). Deterministic:
    ties are always broken toward the earliest-indexed node in `nodes`, so
    the same graph always reports the same path, not merely *a* longest
    one. `[]` for an empty graph."""
    if not nodes:
        return []
    duplicates = find_duplicate_ids(nodes)
    if duplicates:
        raise ValueError(f"cannot compute a critical path: duplicate node ids ({duplicates})")
    cycle = find_cycle(nodes)
    if cycle is not None:
        raise ValueError(f"cannot compute a critical path: cycle detected ({cycle})")
    dangling = find_dangling_dependencies(nodes)
    if dangling:
        raise ValueError(f"cannot compute a critical path: dangling dependencies ({dangling})")

    index = {node.id: i for i, node in enumerate(nodes)}
    by_id = {node.id: node for node in nodes}
    best_effort: dict[UUID, float] = {}
    best_predecessor: dict[UUID, UUID | None] = {}

    def longest_ending_at(node_id: UUID) -> float:
        if node_id in best_effort:
            return best_effort[node_id]
        node = by_id[node_id]
        if not node.depends_on:
            best_effort[node_id] = node.estimated_effort.effort_hours
            best_predecessor[node_id] = None
            return best_effort[node_id]
        best_dep = max(
            node.depends_on, key=lambda dep_id: (longest_ending_at(dep_id), -index[dep_id])
        )
        best_effort[node_id] = node.estimated_effort.effort_hours + best_effort[best_dep]
        best_predecessor[node_id] = best_dep
        return best_effort[node_id]

    for node in nodes:
        longest_ending_at(node.id)

    end_node = max(nodes, key=lambda n: (best_effort[n.id], -index[n.id]))

    path: list[UUID] = []
    current: UUID | None = end_node.id
    while current is not None:
        path.append(current)
        current = best_predecessor[current]
    path.reverse()
    return path

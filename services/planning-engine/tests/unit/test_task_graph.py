from uuid import UUID, uuid4

import pytest
from nova_contracts import RiskLevel
from nova_planning_engine.domain.models import Estimate, TaskNode
from nova_planning_engine.domain.task_graph import (
    compute_critical_path,
    find_cycle,
    find_dangling_dependencies,
    find_duplicate_ids,
    has_cycle,
)


def _node(
    objective: str, *, depends_on: list[UUID] | None = None, effort_hours: float = 1.0
) -> TaskNode:
    return TaskNode(
        objective=objective,
        depends_on=depends_on or [],
        estimated_effort=Estimate(effort_hours=effort_hours, confidence=0.8),
        risk=RiskLevel.LOW,
    )


def test_empty_graph_has_no_cycle_and_empty_critical_path() -> None:
    assert find_cycle([]) is None
    assert has_cycle([]) is False
    assert compute_critical_path([]) == []


def test_single_node_graph_is_its_own_critical_path() -> None:
    node = _node("only task", effort_hours=3.0)
    assert has_cycle([node]) is False
    assert compute_critical_path([node]) == [node.id]


def test_linear_chain_critical_path_is_the_whole_chain_in_order() -> None:
    a = _node("a", effort_hours=1.0)
    b = _node("b", depends_on=[a.id], effort_hours=1.0)
    c = _node("c", depends_on=[b.id], effort_hours=1.0)
    nodes = [a, b, c]

    assert has_cycle(nodes) is False
    assert compute_critical_path(nodes) == [a.id, b.id, c.id]


def test_critical_path_prefers_the_longer_by_effort_branch() -> None:
    """Two independent roots feed one join node -- the critical path must
    follow the branch with the larger cumulative effort_hours, not simply
    the first-listed one, proving this is a real longest-path computation
    and not an arbitrary traversal order."""
    short = _node("short prep", effort_hours=1.0)
    long_branch = _node("long prep", effort_hours=10.0)
    join = _node("integrate", depends_on=[short.id, long_branch.id], effort_hours=2.0)
    nodes = [short, long_branch, join]

    path = compute_critical_path(nodes)
    assert path == [long_branch.id, join.id]


def test_critical_path_tie_break_is_deterministic_toward_earliest_index() -> None:
    """Two branches with identical cumulative effort -- the tie must always
    resolve toward whichever branch appears first in `nodes`, not
    arbitrarily, so the same graph always reports the same path."""
    branch_a = _node("branch a", effort_hours=5.0)
    branch_b = _node("branch b", effort_hours=5.0)
    join = _node("join", depends_on=[branch_a.id, branch_b.id], effort_hours=1.0)
    nodes = [branch_a, branch_b, join]

    path = compute_critical_path(nodes)
    assert path == [branch_a.id, join.id]

    # Reversing the declaration order of the tied branches flips which one
    # wins -- confirming the tie-break really does track list position,
    # not, say, insertion timestamp or UUID ordering.
    reordered = [branch_b, branch_a, join]
    assert compute_critical_path(reordered) == [branch_b.id, join.id]


def test_independent_nodes_have_no_dependency_edges() -> None:
    """Bible Part 2 "independent nodes should execute simultaneously" --
    confirmed structurally representable: two nodes with empty `depends_on`
    are both valid roots, no forced ordering between them."""
    a = _node("a")
    b = _node("b")
    assert a.depends_on == []
    assert b.depends_on == []
    assert has_cycle([a, b]) is False


def test_find_cycle_detects_a_direct_two_node_cycle() -> None:
    a_id, b_id = uuid4(), uuid4()
    a = TaskNode(
        id=a_id,
        objective="a",
        depends_on=[b_id],
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )
    b = TaskNode(
        id=b_id,
        objective="b",
        depends_on=[a_id],
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )
    nodes = [a, b]

    assert has_cycle(nodes) is True
    cycle = find_cycle(nodes)
    assert cycle is not None
    assert set(cycle) == {a_id, b_id}


def test_find_cycle_detects_a_longer_indirect_cycle() -> None:
    a = _node("a")
    b = _node("b", depends_on=[a.id])
    c = _node("c", depends_on=[b.id])
    # Close the loop: a depends on c.
    a_looped = a.model_copy(update={"depends_on": [c.id]})
    nodes = [a_looped, b, c]

    assert has_cycle(nodes) is True


def test_compute_critical_path_raises_on_cycle_instead_of_hanging() -> None:
    a_id, b_id = uuid4(), uuid4()
    a = TaskNode(
        id=a_id,
        objective="a",
        depends_on=[b_id],
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )
    b = TaskNode(
        id=b_id,
        objective="b",
        depends_on=[a_id],
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )
    with pytest.raises(ValueError, match="cycle"):
        compute_critical_path([a, b])


def test_find_dangling_dependencies_reports_missing_targets() -> None:
    missing_id = uuid4()
    node = _node("orphaned dependency", depends_on=[missing_id])

    dangling = find_dangling_dependencies([node])
    assert dangling == {node.id: [missing_id]}


def test_graph_with_no_dangling_dependencies_reports_empty() -> None:
    a = _node("a")
    b = _node("b", depends_on=[a.id])
    assert find_dangling_dependencies([a, b]) == {}


def test_compute_critical_path_raises_on_dangling_dependency() -> None:
    node = _node("orphaned", depends_on=[uuid4()])
    with pytest.raises(ValueError, match="dangling"):
        compute_critical_path([node])


def test_find_duplicate_ids_reports_a_shared_id_once() -> None:
    """A `TaskGraph.nodes` list is a plain `list[TaskNode]` -- nothing at
    the Pydantic level stops two nodes from sharing an `id`. Every function
    in this module keys a `dict` by `node.id`, which would otherwise
    silently drop one of the duplicates rather than surface the error."""
    shared_id = uuid4()
    first = TaskNode(
        id=shared_id,
        objective="first",
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )
    second = TaskNode(
        id=shared_id,
        objective="second",
        estimated_effort=Estimate(effort_hours=2.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )

    assert find_duplicate_ids([first, second]) == [shared_id]


def test_find_duplicate_ids_reports_empty_for_a_well_formed_graph() -> None:
    a, b = _node("a"), _node("b")
    assert find_duplicate_ids([a, b]) == []


def test_compute_critical_path_raises_on_duplicate_node_ids() -> None:
    """Proves the duplicate is rejected outright, not silently resolved by
    keeping whichever node happens to win the `dict`-keyed-by-`id` race --
    the second node's much larger `effort_hours` (99.0) would silently and
    non-deterministically change the reported critical path length if this
    were merely ignored rather than raised."""
    shared_id = uuid4()
    first = TaskNode(
        id=shared_id,
        objective="first",
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )
    second = TaskNode(
        id=shared_id,
        objective="second",
        estimated_effort=Estimate(effort_hours=99.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )

    with pytest.raises(ValueError, match="duplicate"):
        compute_critical_path([first, second])


def test_find_cycle_detects_a_node_that_depends_on_itself() -> None:
    """A degenerate one-node cycle -- `depends_on` containing the node's own
    `id`. Not merely a hypothetical: nothing at the Pydantic level forbids
    it, so the algorithm must reject it explicitly."""
    self_id = uuid4()
    node = TaskNode(
        id=self_id,
        objective="depends on itself",
        depends_on=[self_id],
        estimated_effort=Estimate(effort_hours=1.0, confidence=0.8),
        risk=RiskLevel.LOW,
    )

    assert has_cycle([node]) is True
    cycle = find_cycle([node])
    assert cycle is not None
    assert set(cycle) == {self_id}


def test_cycle_and_critical_path_detection_do_not_depend_on_topological_listing_order() -> None:
    """`nodes` is never required to be pre-sorted into dependency order --
    a join node listed *before* the dependencies it references must be
    detected and traversed correctly by walking into still-unvisited
    (white) dependencies from within a single DFS call, not only by
    relying on the top-level loop having already visited them as roots
    first. This is the shape every prior cycle/critical-path test in this
    file happened not to exercise (every earlier test lists dependencies
    before their dependents)."""
    short = _node("short prep", effort_hours=1.0)
    long_branch = _node("long prep", effort_hours=10.0)
    join = _node("integrate", depends_on=[short.id, long_branch.id], effort_hours=2.0)

    reordered = [join, short, long_branch]

    assert has_cycle(reordered) is False
    assert compute_critical_path(reordered) == [long_branch.id, join.id]


def test_parent_child_relationship_is_expressed_through_depends_on() -> None:
    """A node's `depends_on` is the only relationship mechanism doc06 §3
    defines -- no separate parent/child field exists on `TaskNode`. This
    test documents that fact as a passing behavior, not an assumption:
    dependents reference their prerequisites by ID, prerequisites carry no
    back-reference of their own."""
    prerequisite = _node("prerequisite")
    dependent = _node("dependent", depends_on=[prerequisite.id])

    assert dependent.depends_on == [prerequisite.id]
    assert not hasattr(prerequisite, "children")
    assert not hasattr(prerequisite, "dependents")

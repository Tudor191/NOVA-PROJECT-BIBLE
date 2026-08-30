"""`agent_os.task.completed`'s own TaskNode-lifecycle decision logic (TDD
3E §4/§12, TDD 3B §6.1's own "`planning-engine` subscribes to mutate the
corresponding `TaskNode.status`") -- a pure function, kept separate from
`events/task_completed_handler.py` so the decision itself is unit-testable
without a repository or an Event Bus, the same "domain functions operate on
and return plain values" shape `domain/goals.py` and `domain/task_graph.py`
already establish.

**Ownership.** `planning-engine` owns every `TaskNode.status` transition;
`agent-os/kernel` owns execution and dispatch and never writes planning
state. That split is the documents' own, not a preference imposed here:
TDD 3B §6.1 assigns the mutation to this engine, and TDD 3E §4 ("its
`assigned_task_node_id` is reset to `"ready"` **in `planning-engine`** (via
the same event path §7 uses)") and §12 both route the Kernel's side of it
back through `agent_os.task.completed` rather than a direct write. No new
event or RPC exists for these transitions -- the already-built
transactional outbox republishes `planning.task_graph.created`, which
`agent-os/kernel`'s Scheduler already consumes.

-------------------------------------------------------------------------
**Phase 3 implementation decision, explicit: `outcome="failure"` is
terminal.**

**TDD 3E §12 does not define post-retry failure semantics.** Its failure
table has five rows; only one concerns an execution failure ("Agent
instance crashes mid-task"), and that row prescribes the *opposite* of a
terminal state -- "the crashed instance's `TaskNode` reverts to `"ready"`
for redispatch". There is no row for "the agent failed and the Kernel's
retry path is exhausted", and no row anywhere in TDD 3E produces a
terminal `"failed"` `TaskNode`. TDD 3E contains no occurrence of "retry"
or "exhausted" at all: the bounded single retry is authored by the
implementation (`agent-os/kernel/domain/scheduler.py`'s own "Bounded,
single retry -- never re-consults the Supervisor a second time"), not by
any design document.

This module therefore **narrows** §12's execution-failure behavior, and
says so rather than implying the documents settled it. The narrowing rests
on a property of the shipped Kernel, verified in source rather than
assumed: by the time `outcome="failure"` is published, the failed instance
has already gone through `supervisor_port.plan_restart()` and the bounded
retry. `agent-os/supervisors`' own `domain/restart.py::plan_restart`
returns the failed instance under all three strategies (`one_for_one`
returns it directly; `one_for_all`/`rest_for_one` filter only
`status != "completed"`, and the Kernel stamps the row `"failed"` before
calling), so the retry is always attempted and always exhausted first.

Treating `"failure"` as `"ready"` after that point would hand a
deterministically-failing node back to the Scheduler forever -- dispatch,
fail, retry, fail, reset, dispatch -- with no stopping condition anywhere
in the documents. `"failed"` is terminal instead. This narrowing is
recorded here and in `docs/design/phase-3/17-3e-task-node-lifecycle.md`;
it changes no contract. `AgentOsTaskCompletedPayload` is untouched -- no
new `outcome` value, no new field.
-------------------------------------------------------------------------

Outcome-to-transition summary (the table `resolve_transitions` implements):

- `"success"` -> the node becomes `"completed"`, then every `"pending"`
  node whose dependencies are now all `"completed"` becomes `"ready"`
  (TDD 3B §6.1's mutation; the promotion is TDD 3E §4's own definition of
  `"ready"`, applied to the new state).
- `"failure"` -> the node becomes `"failed"`, terminal (the narrowing
  disclosed above).
- `"interrupted"` -> the node becomes `"ready"` (TDD 3E §4/§12's
  Kernel-restart-reconciliation path, unchanged).
- `"needs_revision"` -> the node becomes `"ready"`: a peer-review verdict
  explicitly asking for another execution round (`scheduler.py` publishes
  it only for a `rejected` review), not an instance fault.
- anything else -> no transitions; an unrecognised outcome never silently
  mutates state.

A `TaskNode` already `"completed"` is never transitioned by any outcome --
the idempotency guard that keeps a redelivered `agent_os.task.completed`
(NATS JetStream at-least-once) from undoing finished work or
re-dispatching an instance that already ran.
"""

from __future__ import annotations

from uuid import UUID

from nova_planning_engine.domain.models import TaskNode, TaskNodeStatus
from nova_planning_engine.domain.task_graph import promotable_ids

__all__ = ["OUTCOME_TRANSITIONS", "TERMINAL_STATUSES", "resolve_transitions"]

TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed"})
"""Statuses no `agent_os.task.completed` outcome ever transitions away
from. `"completed"` is the redelivery guard; `"failed"` is terminal by the
decision recorded in this module's own docstring."""

OUTCOME_TRANSITIONS: dict[str, TaskNodeStatus] = {
    "success": "completed",
    "failure": "failed",
    "interrupted": "ready",
    "needs_revision": "ready",
}
"""The direct outcome -> status mapping. Dependent-node promotion is not
in here: it is derived from the resulting graph, not from the outcome."""


def resolve_transitions(
    *, outcome: str, task_node_id: UUID, nodes: list[TaskNode]
) -> list[tuple[UUID, TaskNodeStatus]]:
    """Every `(task_node_id, new_status)` pair the `agent_os.task.completed`
    handler should apply, in application order -- the completed node first,
    then any dependents its completion unblocks. `[]` means "this event
    changes nothing", which the handler treats as a successfully-processed
    event, never an error.

    `nodes` is the full node list of the graph containing `task_node_id`
    (as returned by `PlanningRepository.find_node`), because promotion is a
    whole-graph question: a dependent is promotable only once *every* one
    of its dependencies is `"completed"`, which cannot be decided from the
    single completing node alone."""
    node = next((candidate for candidate in nodes if candidate.id == task_node_id), None)
    if node is None:
        return []
    if node.status in TERMINAL_STATUSES:
        return []

    new_status = OUTCOME_TRANSITIONS.get(outcome)
    if new_status is None:
        return []

    transitions: list[tuple[UUID, TaskNodeStatus]] = [(task_node_id, new_status)]
    if new_status != "completed":
        return transitions

    # Promotion is evaluated against the graph *as it will be* once this
    # node is `"completed"` -- the whole point is to find dependents whose
    # last outstanding dependency is the one that just finished.
    after = [
        candidate.model_copy(update={"status": "completed"})
        if candidate.id == task_node_id
        else candidate
        for candidate in nodes
    ]
    transitions.extend((node_id, "ready") for node_id in promotable_ids(after))
    return transitions

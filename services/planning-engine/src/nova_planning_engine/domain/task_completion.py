"""`agent_os.task.completed`'s own restart-resume decision logic (TDD 3E
§4/§12) -- a pure function, kept separate from `events/
task_completed_handler.py` so the decision itself is unit-testable without
a repository or an Event Bus, the same "domain functions operate on and
return plain values" shape `domain/goals.py` and `domain/task_graph.py`
already establish.

Precisely bounded to restart-resume, not "Full Dynamic Replanning"
(`05-tdd-3b-planning-engine.md`'s own explicit exclusion list, §7): only
`outcome in {"interrupted", "failure"}` ever resets a `TaskNode` to
`"ready"` --

- `"interrupted"` is TDD 3E §4/§12's own named Kernel-restart-reconciliation
  scenario: the `agent_instance` row died with the old Kernel process, no
  `AgentResult` was ever produced, and the `TaskNode` "must revert to
  `'ready'` for redispatch, never left `'running'` forever"
  (`nova_contracts.events.agent_os.AgentOsTaskCompletedPayload`'s own
  docstring).
- `"failure"` is TDD 3E §12's own failure-table row ("Agent instance
  crashes mid-task... the crashed instance's `TaskNode` reverts to
  `'ready'` for redispatch") -- covers the case where the owning
  Supervisor's bounded single retry (`agent-os/kernel/domain/scheduler.py::
  dispatch_task_node`) was exhausted without success.
- `"success"` is deliberately never reset here -- disclosed, not silently
  invented: nothing in this codebase yet marks a `TaskNode` `"completed"`
  on success (a genuinely separate, unbuilt piece of "Full Dynamic
  Replanning"); this function only ever prevents a regression away from
  whatever status a node already has, it never advances one.
- `"needs_revision"` is a peer-review quality signal (TDD 3E §12), not an
  instance fault -- no document describes a revision-loop recovery path,
  and blindly redispatching it via the generic Scheduler is not
  necessarily that path, so it is left untouched here too.

A `TaskNode` already `"completed"` is never reset regardless of `outcome`
-- "preserve completed work, do not duplicate completed agent instances"
-- the one idempotency guard this function enforces beyond the outcome
check itself.
"""

from __future__ import annotations

__all__ = ["RESUME_TRIGGERING_OUTCOMES", "should_reset_to_ready"]

RESUME_TRIGGERING_OUTCOMES: frozenset[str] = frozenset({"interrupted", "failure"})


def should_reset_to_ready(*, outcome: str, current_status: str) -> bool:
    """`True` iff `agent_os.task.completed`'s handler should reset this
    `TaskNode` to `"ready"` and republish `planning.task_graph.created`."""
    if outcome not in RESUME_TRIGGERING_OUTCOMES:
        return False
    return current_status != "completed"

"""Restart-strategy planning -- doc 12 §9, verbatim three-strategy set,
"directly borrowed from OTP because the problem is identical." Pure
functions: given a failed instance and its siblings (instances sharing the
same Supervisor/category group), compute which instance ids the Supervisor
must restart. Never touches Kernel's own `agent_instance` persistence or
execution backend directly -- `main.py`'s handler is what calls
`AgentInstancePort.restart()` for each id this returns; see `domain/ports.py`'s
own docstring for that Protocol's current real-caller-but-no-real-callee
status.
"""

from __future__ import annotations

from uuid import UUID

from nova_agent_os_supervisors.domain.models import RestartStrategy, SupervisedInstance

__all__ = ["plan_restart"]


def plan_restart(
    *,
    strategy: RestartStrategy,
    failed_instance_id: UUID,
    siblings: list[SupervisedInstance],
) -> list[UUID]:
    """`siblings` includes the failed instance itself. Returns the ids to
    restart, in a stable order (failed instance first, then siblings by
    `started_order`) -- never includes an already-`"completed"` sibling
    (only `"running"`/`"failed"` instances are ever restart candidates)."""
    failed = next((s for s in siblings if s.id == failed_instance_id), None)
    if failed is None:
        raise ValueError(f"failed_instance_id {failed_instance_id} is not among siblings")

    candidates = [s for s in siblings if s.status != "completed"]

    if strategy is RestartStrategy.ONE_FOR_ONE:
        return [failed.id]

    if strategy is RestartStrategy.ONE_FOR_ALL:
        ordered = sorted(candidates, key=lambda s: s.started_order)
        return [s.id for s in ordered]

    # REST_FOR_ONE: the failed instance and everything started after it.
    ordered = sorted(
        (s for s in candidates if s.started_order >= failed.started_order),
        key=lambda s: s.started_order,
    )
    return [s.id for s in ordered]

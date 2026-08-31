"""Conflict resolution -- doc 12 §9, exactly two levels: "escalates first
to the owning Supervisor (which has domain context and can often resolve
it directly -- e.g., the Engineering Supervisor knows Coding Agent's
output failed QA agent's test and can decide without going further up),
and only escalates to `reasoning-engine` for an evidence-weighted decision
... when the Supervisor itself cannot resolve it -- recorded to Decision
Memory (Part 3) either way."

**Local-resolution heuristic, disclosed.** Doc 12 §9 gives exactly one
concrete worked example (Coding Agent vs. QA Agent, above) and no general
algorithm. The heuristic below implements that example literally and
generalizes it by the smallest possible step: when the two conflicting
`AgentResult`s disagree on `status` (one `"success"`, the other
`"failure"`/`"needs_revision"`), the failure signal is objective evidence
(e.g. a failing test) and is trusted without escalation -- exactly the
QA-vs-Coding case. When both results report the *same* `status` but
disagree in substance (`output`), the Supervisor has no textually-grounded
basis to prefer one over the other and escalates, per doc 12's own
"only ... when the Supervisor itself cannot resolve it" instruction. This
is a proposed, disclosed minimal implementation of an intentionally
underspecified heuristic -- not a redesign of the two-level escalation
architecture itself (TDD 3E §7's own resolved shape), flagged for Gate
Review confirmation.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import AgentResult

from nova_agent_os_supervisors.domain.models import ConflictRecord
from nova_agent_os_supervisors.domain.ports import DecisionMemoryPort, ReasoningPort

__all__ = ["resolve_conflict"]

_FAILING_STATUSES = {"failure", "needs_revision"}


async def resolve_conflict(
    *,
    description: str,
    result_a: AgentResult,
    result_b: AgentResult,
    reasoning_port: ReasoningPort,
    decision_memory_port: DecisionMemoryPort,
    user_id: UUID,
    correlation_id: UUID,
) -> ConflictRecord:
    a_failing = result_a.status in _FAILING_STATUSES
    b_failing = result_b.status in _FAILING_STATUSES

    if a_failing != b_failing:
        trusted = result_a if a_failing else result_b
        outcome = (
            f"resolved locally: trusted the failing result "
            f"(agent_instance_id={trusted.agent_instance_id}, status={trusted.status}) "
            "as objective evidence over the conflicting success claim (doc 12 §9's "
            "own QA-vs-Coding example)"
        )
        record = ConflictRecord(
            description=description,
            resolution="supervisor_resolved",
            outcome=outcome,
            correlation_id=correlation_id,
        )
    else:
        reasoning_outcome = await reasoning_port.reason(
            objective_text=(
                f"{description} Both agent results reported status={result_a.status!r}; "
                f"result A output={result_a.output!r}, result B output={result_b.output!r}. "
                "Which is correct?"
            ),
            user_id=user_id,
            correlation_id=correlation_id,
        )
        outcome = (
            f"escalated to reasoning-engine: outcome={reasoning_outcome.outcome!r}, "
            f"chosen_description={reasoning_outcome.chosen_description!r}"
        )
        record = ConflictRecord(
            description=description,
            resolution="escalated_to_reasoning",
            outcome=outcome,
            correlation_id=correlation_id,
        )

    await decision_memory_port.record(
        objective=description,
        alternatives=[str(result_a.output), str(result_b.output)],
        chosen_alternative=record.outcome,
        reasoning=record.outcome,
        correlation_id=correlation_id,
    )
    return record

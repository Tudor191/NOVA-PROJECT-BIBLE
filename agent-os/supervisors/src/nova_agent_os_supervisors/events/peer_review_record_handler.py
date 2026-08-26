"""`agent_os.supervisor.peer_review.request` RPC handler -- disclosed
addition, coding-agent slice. See `nova_contracts.events.agent_os`'s own
`AgentOsPeerReviewRequestPayload` docstring for the full ownership-split
disclosure: Kernel performs the mechanical work (resolves and spawns a
reviewer via its own `AgentExecutionBackend`), reports the raw outcome
here, and this Supervisor -- not Kernel -- makes the accept/reject
classification (`domain/peer_review.py::classify_reviewer_result`, shared
with `run_peer_review_round`'s own identical rule) and records to Decision
Memory (doc 12 §9: "Recorded to Decision Memory either way"), matching
every conflict-resolution round's own identical treatment
(`domain/conflict.py::resolve_conflict`).
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from nova_contracts import (
    AgentOsPeerReviewReplyPayload,
    AgentOsPeerReviewRequestPayload,
    EventEnvelope,
)

from nova_agent_os_supervisors.domain.peer_review import classify_reviewer_result

__all__ = ["make_peer_review_record_handler"]


def make_peer_review_record_handler(app: FastAPI):  # type: ignore[no-untyped-def]
    async def handle(envelope: EventEnvelope) -> AgentOsPeerReviewReplyPayload:
        payload = AgentOsPeerReviewRequestPayload.model_validate(envelope.payload)
        state = app.state

        peer_validation: Literal["approved", "rejected", "timed_out"]
        if not payload.reviewer_available:
            peer_validation = "timed_out"
        else:
            peer_validation = classify_reviewer_result(payload.reviewer_result)

        alternatives = [str(payload.primary_result.output)]
        if payload.reviewer_result is not None:
            alternatives.append(str(payload.reviewer_result.output))
        await state.decision_memory_port.record(
            objective=(
                f"peer review of agent_instance_id={payload.primary_result.agent_instance_id} "
                f"by reviewer_category={payload.reviewer_category!r}"
            ),
            alternatives=alternatives,
            chosen_alternative=f"peer_validation={peer_validation}",
            reasoning=f"peer_validation={peer_validation}",
            correlation_id=payload.correlation_id,
        )

        return AgentOsPeerReviewReplyPayload(peer_validation=peer_validation)

    return handle

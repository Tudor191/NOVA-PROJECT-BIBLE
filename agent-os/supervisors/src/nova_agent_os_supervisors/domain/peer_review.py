"""One peer-review round -- doc 12 §9: "the Engineering Supervisor sends
`PEER_REVIEW_REQUEST` (Agent Mailbox) to a reviewer instance, collects its
`AgentResult` before accepting the primary result." TDD 3E §12: a timing-
out reviewer is a real, disclosed, non-fatal outcome -- the Supervisor
proceeds with the primary result, never silently treating a timeout as an
approving review.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_contracts import AgentMessage, AgentMessageType, AgentResult

from nova_agent_os_supervisors.domain.models import PeerReviewOutcome
from nova_agent_os_supervisors.domain.ports import AgentInstancePort

__all__ = ["run_peer_review_round"]


async def run_peer_review_round(
    primary_result: AgentResult,
    *,
    reviewer_instance_id: UUID,
    instance_port: AgentInstancePort,
    supervisor_instance_id: UUID | None = None,
    timeout_ms: int = 30000,
    correlation_id: UUID | None = None,
) -> PeerReviewOutcome:
    request = AgentMessage(
        message_type=AgentMessageType.PEER_REVIEW_REQUEST,
        from_instance_id=supervisor_instance_id,
        to_instance_id=reviewer_instance_id,
        payload=primary_result.model_dump(mode="json"),
        correlation_id=correlation_id or uuid4(),
    )
    try:
        reply = await instance_port.deliver(request, timeout_ms=timeout_ms)
    except TimeoutError:
        return PeerReviewOutcome(
            primary_result=primary_result,
            reviewer_instance_id=reviewer_instance_id,
            peer_validation="timed_out",
            reviewer_result=None,
        )

    if reply is None or reply.message_type is not AgentMessageType.PEER_REVIEW_RESULT:
        return PeerReviewOutcome(
            primary_result=primary_result,
            reviewer_instance_id=reviewer_instance_id,
            peer_validation="timed_out",
            reviewer_result=None,
        )

    reviewer_result = AgentResult.model_validate(reply.payload)
    peer_validation = "approved" if reviewer_result.status == "success" else "rejected"
    return PeerReviewOutcome(
        primary_result=primary_result,
        reviewer_instance_id=reviewer_instance_id,
        peer_validation=peer_validation,
        reviewer_result=reviewer_result,
    )

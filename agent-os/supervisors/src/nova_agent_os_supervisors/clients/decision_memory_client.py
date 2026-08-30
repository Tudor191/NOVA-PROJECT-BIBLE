"""`LoggingDecisionMemoryClient` -- `domain.ports.DecisionMemoryPort`
default implementation. See `domain/ports.py`'s own module docstring:
`memory-engine` exposes no create/record RPC another engine can call, so
this records a structured log line rather than performing a live
cross-engine call -- a real, disclosed gap, not a silently skipped step.
Doc 12 §9's "Recorded to Decision Memory either way" is honored at the
Supervisor's own boundary (every conflict resolution calls this port);
wiring an actual `memory-engine` RPC is `memory-engine`'s own separate,
disclosed follow-up.
"""

from __future__ import annotations

from uuid import UUID

from nova_observability import get_logger

__all__ = ["LoggingDecisionMemoryClient"]

logger = get_logger("supervisors")


class LoggingDecisionMemoryClient:
    async def record(
        self,
        *,
        objective: str,
        alternatives: list[str],
        chosen_alternative: str,
        reasoning: str,
        correlation_id: UUID,
    ) -> None:
        logger.info(
            "decision_memory_record (no live memory-engine RPC exists -- local log only): "
            "objective=%r chosen_alternative=%r correlation_id=%s",
            objective,
            chosen_alternative,
            correlation_id,
        )

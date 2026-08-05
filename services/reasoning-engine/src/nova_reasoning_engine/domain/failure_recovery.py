"""Failure Handling (docs/design/phase-2b/00-reasoning-engine.md §17) -- Bible
Part 8's explicit failure-recovery action set, applied to any pipeline-stage
failure: an upstream port timeout, a hypothesis-generation call returning
nothing usable, or a fully constraint-rejected alternative pool.

`delegate` is never selected by `recommend_recovery` in Phase 2B -- it is a
named future extension point (§25, depends on NAOS, Phase 3) that stays
honestly unavailable rather than stubbed with fake behavior.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import FailureAction, FailureRecovery

__all__ = ["MAX_RETRIES", "recommend_recovery"]

MAX_RETRIES = 2
"""A bounded retry walk, mirroring the AI Model Orchestration Engine's own
fallback-chain shape -- every attempt is recorded (§19), never silent, and
never unbounded."""


def recommend_recovery(*, stage: str, reason: str, retry_count: int) -> FailureRecovery:
    """Maps a failed pipeline stage to Part 8's recovery action set. Once
    `retry_count` reaches `MAX_RETRIES`, always defers to
    `request_clarification` rather than retrying indefinitely."""
    if retry_count >= MAX_RETRIES:
        action = FailureAction.REQUEST_CLARIFICATION
    elif stage == "context_assembling":
        action = FailureAction.RESTART
    elif stage == "hypotheses_generating":
        action = FailureAction.REDUCE_COMPLEXITY
    elif stage in {"alternatives_evaluating", "decision_scoring"} and "evidence" in reason.lower():
        action = FailureAction.RETRIEVE_MORE_KNOWLEDGE
    elif stage in {"alternatives_evaluating", "decision_scoring"}:
        action = FailureAction.ESCALATE_DEEPER
    else:
        action = FailureAction.RESTART

    return FailureRecovery(stage=stage, action=action, reason=reason, retry_count=retry_count)

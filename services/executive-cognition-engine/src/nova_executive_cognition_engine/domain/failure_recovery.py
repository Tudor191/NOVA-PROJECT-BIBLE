"""Failure handling (docs/design/phase-2c/00-executive-cognition-engine.md
§14) -- mirrors Reasoning Engine's own six-action failure-recovery
vocabulary exactly (that engine's §17), reused rather than reinvented,
applied to arbitration-stage failures instead of reasoning-stage ones.

`delegate` is never selected here, the identical honest gap Reasoning
Engine's own module carries -- a named future extension point (design doc
§24, depends on NAOS, Phase 3).
"""

from __future__ import annotations

from nova_executive_cognition_engine.domain.models import ExecutiveFailureRecovery, FailureAction

__all__ = ["recommend_recovery"]


def recommend_recovery(
    *, stage: str, reason: str, retry_count: int = 0
) -> ExecutiveFailureRecovery:
    """Maps a failed arbitration stage to the recovery action set (§14's
    table): an upstream port timeout during context-gathering restarts
    (context degrades gracefully, per every prior engine's own precedent); a
    malformed request requests clarification rather than guessing a missing
    priority factor (§6's "never invented by this engine" rule); an
    unresolved conflict escalates deeper (`ESCALATED`, §7, §13); anything
    else restarts."""
    if stage == "context_gathering":
        action = FailureAction.RESTART
    elif stage == "request_validation":
        action = FailureAction.REQUEST_CLARIFICATION
    elif stage == "conflict_resolution":
        action = FailureAction.ESCALATE_DEEPER
    else:
        action = FailureAction.RESTART

    return ExecutiveFailureRecovery(
        stage=stage, action=action, reason=reason, retry_count=retry_count
    )

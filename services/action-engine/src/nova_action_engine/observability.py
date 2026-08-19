"""Observability instruments (TDD 3D §9): the 6 named metrics, plus
`create_metrics()` following every other engine's own `observability.py`
convention. Must only be called after `configure_observability()` has
run. `domain/` never imports this module -- `main.py` reads the
instruments off `app.state.metrics`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter

__all__ = ["ActionEngineMetrics", "create_metrics"]


@dataclass(frozen=True)
class ActionEngineMetrics:
    action_execute_total: Counter
    """Labeled by `action_type` and `outcome` -- TDD 3D §9's named metric."""

    action_approval_requested_total: Counter
    """Labeled by `risk`."""

    action_approval_decided_total: Counter
    """Labeled by `decision`."""

    action_approval_timeout_total: Counter
    """The fail-closed path (§4) -- an approval timeout, counted
    distinctly from an explicit denial."""

    action_rollback_invoked_total: Counter
    """Labeled by `kind` (`RollbackStrategy.kind`)."""

    action_identity_confidence_denied_total: Counter
    """Labeled by `risk` -- ADR-032 gate rejections (§7)."""


def create_metrics() -> ActionEngineMetrics:
    meter = get_meter("action-engine")
    return ActionEngineMetrics(
        action_execute_total=meter.create_counter(
            "action_execute_total",
            description="action.execute invocations, labeled by action_type and outcome.",
        ),
        action_approval_requested_total=meter.create_counter(
            "action_approval_requested_total",
            description="Approval-loop requests, labeled by risk.",
        ),
        action_approval_decided_total=meter.create_counter(
            "action_approval_decided_total",
            description="Approval-loop decisions, labeled by decision.",
        ),
        action_approval_timeout_total=meter.create_counter(
            "action_approval_timeout_total",
            description="Approval-loop timeouts (fail-closed path).",
        ),
        action_rollback_invoked_total=meter.create_counter(
            "action_rollback_invoked_total",
            description="Rollback invocations, labeled by RollbackStrategy.kind.",
        ),
        action_identity_confidence_denied_total=meter.create_counter(
            "action_identity_confidence_denied_total",
            description="ADR-032 identity-confidence gate rejections, labeled by risk.",
        ),
    )

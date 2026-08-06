"""Observability instruments -- docs/architecture/15-development-workflow.md §9
item 10.

`create_metrics()` must only be called *after* `configure_observability()` has
run, mirroring every other engine's own `observability.py`. `api/`, `events/`,
and `workers/` read the resulting instruments off `app.state.metrics` / a
passed-in `ExecutiveCognitionEngineMetrics`; `domain/` never imports this
module -- the structured per-decision record lives in `ExecutiveDecisionTrace`
(§18), not in these aggregate counters, which are for operational dashboards
only.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class ExecutiveCognitionEngineMetrics:
    arbitration_duration_seconds: Histogram
    """§20: end-to-end latency of one `arbitrate_request` call."""

    arbitration_decisions_total: Counter
    """Labeled by `outcome` (`proceed` | `proceed_reduced` | `wait` | `escalated`, §4)."""

    composite_priority_score: Histogram
    """The composite Cognitive Priority Matrix score (§6) of every scored contender."""

    long_term_alignment_score: Histogram
    """ADR-029's own factor (§6.1), tracked separately to make its real-world
    effect (versus a permanently-inert `0.0`) observable."""

    policies_applied_total: Counter
    """Labeled by `policy` (§12: `user_goals_override_optimization` |
    `safety_overrides_speed`)."""

    conflicts_escalated_total: Counter
    """§10: conflicts that exhausted all five signals and reached `ESCALATED`."""

    human_overrides_total: Counter
    """Labeled by `action` (`confirm` | `redirect` | `reject`, §13)."""

    failures_total: Counter
    """Labeled by `stage` (§14)."""

    outbox_dispatched_total: Counter
    """Labeled by `subject`."""


def create_metrics() -> ExecutiveCognitionEngineMetrics:
    meter = get_meter("executive-cognition-engine")
    return ExecutiveCognitionEngineMetrics(
        arbitration_duration_seconds=meter.create_histogram(
            "executive_cognition_engine_arbitration_duration_seconds",
            description="End-to-end latency of one arbitration decision.",
            unit="s",
        ),
        arbitration_decisions_total=meter.create_counter(
            "executive_cognition_engine_arbitration_decisions_total",
            description="Arbitration decisions produced, labeled by outcome.",
        ),
        composite_priority_score=meter.create_histogram(
            "executive_cognition_engine_composite_priority_score",
            description="Composite Cognitive Priority Matrix score of every scored contender.",
        ),
        long_term_alignment_score=meter.create_histogram(
            "executive_cognition_engine_long_term_alignment_score",
            description="ADR-029's long_term_alignment factor of every scored contender.",
        ),
        policies_applied_total=meter.create_counter(
            "executive_cognition_engine_policies_applied_total",
            description="Executive policies applied, labeled by policy name.",
        ),
        conflicts_escalated_total=meter.create_counter(
            "executive_cognition_engine_conflicts_escalated_total",
            description="Conflicts that could not be resolved and were escalated.",
        ),
        human_overrides_total=meter.create_counter(
            "executive_cognition_engine_human_overrides_total",
            description="Human overrides applied, labeled by action.",
        ),
        failures_total=meter.create_counter(
            "executive_cognition_engine_failures_total",
            description="Arbitration failures, labeled by stage.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "executive_cognition_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus, labeled by subject.",
        ),
    )

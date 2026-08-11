"""Observability instruments -- docs/architecture/15-development-workflow.md
Sec9.0 item 10.

`create_metrics()` must only be called *after* `configure_observability()`
has run, mirroring every other engine's own `observability.py`. `api/` and
`events/` read the resulting instruments off `app.state.metrics`; `domain/`
never imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class DigitalTwinEngineMetrics:
    session_completed_processing_duration_seconds: Histogram
    """End-to-end latency of one `communication.session.completed` handler
    invocation (evidence recording + trust-metric recompute)."""

    trust_metric_recomputed_total: Counter
    """Every time `trust_metric.compute_trust_metric` runs, labeled by
    whether `correction_frequency` actually changed from the prior stored
    value (`outcome`: `"changed"` | `"unchanged"`)."""

    proactive_suggestion_decisions_total: Counter
    """Labeled by `outcome` (`"allowed"` | `"denied"`) -- Sec10.1's
    boundary-policy verdicts."""

    outbox_dispatched_total: Counter
    """`nova_service_kit.outbox.OutboxMetrics`'s own required field -- the
    shared `dispatch_ready_events` loop (`repository/outbox_dispatcher.py`)
    records into this every poll, structurally matched, no inheritance
    (ADR-034)."""


def create_metrics() -> DigitalTwinEngineMetrics:
    meter = get_meter("digital-twin-engine")
    return DigitalTwinEngineMetrics(
        session_completed_processing_duration_seconds=meter.create_histogram(
            "digital_twin_engine_session_completed_processing_duration_seconds",
            description="End-to-end latency of one communication.session.completed handler call.",
            unit="s",
        ),
        trust_metric_recomputed_total=meter.create_counter(
            "digital_twin_engine_trust_metric_recomputed_total",
            description="Trust-metric recomputations, labeled by whether the value changed.",
        ),
        proactive_suggestion_decisions_total=meter.create_counter(
            "digital_twin_engine_proactive_suggestion_decisions_total",
            description="Proactive-suggestion boundary-policy verdicts, labeled by outcome.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "digital_twin_engine_outbox_dispatched_total",
            description="Outbox rows dispatched to the Event Bus.",
        ),
    )

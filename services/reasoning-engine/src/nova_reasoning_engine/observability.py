"""Observability instruments -- docs/architecture/15-development-workflow.md §9
item 10.

`create_metrics()` must only be called *after* `configure_observability()` has
run, mirroring every other engine's own `observability.py`. `api/`, `events/`,
and `workers/` read the resulting instruments off `app.state.metrics` / a
passed-in `ReasoningEngineMetrics`; `domain/` never imports this module --
the structured per-process record lives in `ReasoningTrace` (§19), not in
these aggregate counters, which are for operational dashboards only.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram

from nova_reasoning_engine.domain.models import ReasoningMode, ReasoningTrace
from nova_reasoning_engine.domain.trace import chain_depth


@dataclass(frozen=True)
class ReasoningEngineMetrics:
    reasoning_request_duration_seconds: Histogram
    """Labeled by `reasoning_mode` (§6)."""

    reasoning_requests_total: Counter
    """Labeled by `outcome` (`decided` | `degraded` | `failed` | `abandoned`, §5)."""

    confidence_score: Histogram
    """The composite confidence score (§10) of every completed reasoning process."""

    hypotheses_generated_total: Counter
    alternatives_generated_total: Counter
    alternatives_below_minimum_total: Counter
    """§14: alternative generation could not reach the minimum even after its
    bounded retry."""

    constraint_violations_total: Counter
    """§9: alternatives rejected by the hard constraint gate."""

    human_overrides_total: Counter
    """Labeled by `action` (`confirm` | `redirect` | `reject`, §18)."""

    failures_total: Counter
    """Labeled by `stage` (§17)."""

    outbox_dispatched_total: Counter
    """Labeled by `subject`."""

    reasoning_multistep_recursion_triggered_total: Counter
    """Phase 3A (§11): incremented once per recursion step taken across a
    Multi-step chain -- derived from `trace.chain_depth()` after `run()`
    returns, the same "read the aggregate off the returned trace/decision"
    pattern `reasoning_requests_total` above already uses."""

    reasoning_multistep_recursion_depth: Histogram
    """Phase 3A: final chain depth reached per completed Multi-step process
    (0 = never recursed)."""

    reasoning_multistep_recursion_exhausted_total: Counter
    """Phase 3A: incremented when a Multi-step chain hit `MultiStepConfig.
    max_step_depth` while still below `verify_threshold`, so no further
    recursion was attempted (`ReasoningTrace.multistep_recursion_exhausted`)."""


def create_metrics() -> ReasoningEngineMetrics:
    meter = get_meter("reasoning-engine")
    return ReasoningEngineMetrics(
        reasoning_request_duration_seconds=meter.create_histogram(
            "reasoning_engine_reasoning_request_duration_seconds",
            description="End-to-end latency of a completed reasoning process, labeled by mode.",
            unit="s",
        ),
        reasoning_requests_total=meter.create_counter(
            "reasoning_engine_reasoning_requests_total",
            description="Completed reasoning processes, labeled by outcome.",
        ),
        confidence_score=meter.create_histogram(
            "reasoning_engine_confidence_score",
            description="Composite confidence score of completed reasoning processes.",
        ),
        hypotheses_generated_total=meter.create_counter(
            "reasoning_engine_hypotheses_generated_total",
            description="Hypotheses generated across all reasoning processes.",
        ),
        alternatives_generated_total=meter.create_counter(
            "reasoning_engine_alternatives_generated_total",
            description="Alternatives generated across all reasoning processes.",
        ),
        alternatives_below_minimum_total=meter.create_counter(
            "reasoning_engine_alternatives_below_minimum_total",
            description="Reasoning processes that could not reach the minimum alternative count.",
        ),
        constraint_violations_total=meter.create_counter(
            "reasoning_engine_constraint_violations_total",
            description="Alternatives rejected by the hard constraint gate.",
        ),
        human_overrides_total=meter.create_counter(
            "reasoning_engine_human_overrides_total",
            description="Human overrides applied, labeled by action.",
        ),
        failures_total=meter.create_counter(
            "reasoning_engine_failures_total",
            description="Reasoning process failures, labeled by stage.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "reasoning_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus, labeled by subject.",
        ),
        reasoning_multistep_recursion_triggered_total=meter.create_counter(
            "reasoning_engine_multistep_recursion_triggered_total",
            description="Multi-step recursion steps taken across all reasoning processes.",
        ),
        reasoning_multistep_recursion_depth=meter.create_histogram(
            "reasoning_engine_multistep_recursion_depth",
            description="Final Multi-step recursion chain depth reached per completed process.",
        ),
        reasoning_multistep_recursion_exhausted_total=meter.create_counter(
            "reasoning_engine_multistep_recursion_exhausted_total",
            description=(
                "Multi-step chains that hit max_step_depth while still below "
                "verify_threshold, so recursion could not continue."
            ),
        ),
    )


def record_multistep_recursion_metrics(
    trace: ReasoningTrace, metrics: ReasoningEngineMetrics
) -> None:
    """Phase 3A (§11): called once per completed top-level `pipeline.run()`
    invocation, from `api/reason.py` and `events/handlers.py` -- never from
    `domain/`, which may not import this module. A no-op for any non-Multi-step
    trace or one that never recursed, the same "derive from the returned
    trace" shape `reasoning_requests_total`'s own call sites already use."""
    if trace.reasoning_mode is not ReasoningMode.MULTI_STEP:
        return
    depth_reached = chain_depth(trace)
    metrics.reasoning_multistep_recursion_depth.record(depth_reached)
    if depth_reached:
        metrics.reasoning_multistep_recursion_triggered_total.add(depth_reached)
    if trace.multistep_recursion_exhausted:
        metrics.reasoning_multistep_recursion_exhausted_total.add(1)

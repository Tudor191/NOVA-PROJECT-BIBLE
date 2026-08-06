"""Observability instruments -- docs/architecture/15-development-workflow.md §9
item 10.

`create_metrics()` must only be called *after* `configure_observability()` has
run, mirroring every other engine's own `observability.py`. `api/`, `events/`,
and `workers/` read the resulting instruments off `app.state.metrics` / a
passed-in `AiModelOrchestrationEngineMetrics`; `domain/` never imports this
module (ADR-021's structured telemetry lives in `UsageRecord`/`usage_record`,
not in these aggregate counters -- these are for operational dashboards, not
the per-request record itself).
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class AiModelOrchestrationEngineMetrics:
    generate_request_duration_seconds: Histogram
    embed_request_duration_seconds: Histogram
    transcribe_request_duration_seconds: Histogram
    synthesize_request_duration_seconds: Histogram
    """Explicitly measured, not folded into a generic histogram, per
    docs/design/phase-2d/00-master-blueprint.md §13.2 (low latency is part of
    NOVA's personality) -- the speech path's latency is exactly the number that
    principle is checked against, so it gets its own dashboard-visible metric
    from day one, the same standard `generate`/`embed` are already held to."""

    requests_total: Counter
    """Labeled by `outcome` (`success` | `fallback` | `failed`)."""

    fallback_used_total: Counter
    retries_total: Counter

    input_tokens_total: Counter
    output_tokens_total: Counter
    estimated_cost_total: Counter
    """Labeled by `provider`."""

    health_checks_total: Counter
    """Labeled by `status` (`healthy` | `degraded` | `unhealthy`)."""

    benchmark_runs_total: Counter

    models_registered_total: Counter
    models_deregistered_total: Counter

    budget_exceeded_total: Counter

    outbox_dispatched_total: Counter
    """Labeled by `subject`."""


def create_metrics() -> AiModelOrchestrationEngineMetrics:
    meter = get_meter("ai-model-orchestration-engine")
    return AiModelOrchestrationEngineMetrics(
        generate_request_duration_seconds=meter.create_histogram(
            "ai_model_orchestration_engine_generate_request_duration_seconds",
            description="End-to-end latency of a routed generate request.",
            unit="s",
        ),
        embed_request_duration_seconds=meter.create_histogram(
            "ai_model_orchestration_engine_embed_request_duration_seconds",
            description="End-to-end latency of a routed embed request.",
            unit="s",
        ),
        transcribe_request_duration_seconds=meter.create_histogram(
            "ai_model_orchestration_engine_transcribe_request_duration_seconds",
            description="End-to-end latency of a routed speech-to-text request.",
            unit="s",
        ),
        synthesize_request_duration_seconds=meter.create_histogram(
            "ai_model_orchestration_engine_synthesize_request_duration_seconds",
            description="End-to-end latency of a routed text-to-speech request.",
            unit="s",
        ),
        requests_total=meter.create_counter(
            "ai_model_orchestration_engine_requests_total",
            description="Routed requests, labeled by outcome.",
        ),
        fallback_used_total=meter.create_counter(
            "ai_model_orchestration_engine_fallback_used_total",
            description="Requests that required at least one fallback attempt.",
        ),
        retries_total=meter.create_counter(
            "ai_model_orchestration_engine_retries_total",
            description="Total connector attempts beyond the first, across all requests.",
        ),
        input_tokens_total=meter.create_counter(
            "ai_model_orchestration_engine_input_tokens_total",
            description="Cumulative input tokens across all requests.",
        ),
        output_tokens_total=meter.create_counter(
            "ai_model_orchestration_engine_output_tokens_total",
            description="Cumulative output tokens across all requests.",
        ),
        estimated_cost_total=meter.create_counter(
            "ai_model_orchestration_engine_estimated_cost_total",
            description="Cumulative estimated cost, labeled by provider.",
        ),
        health_checks_total=meter.create_counter(
            "ai_model_orchestration_engine_health_checks_total",
            description="Connector health probes, labeled by resulting status.",
        ),
        benchmark_runs_total=meter.create_counter(
            "ai_model_orchestration_engine_benchmark_runs_total",
            description="Benchmark evaluation runs completed.",
        ),
        models_registered_total=meter.create_counter(
            "ai_model_orchestration_engine_models_registered_total",
            description="Models registered into the Model Registry.",
        ),
        models_deregistered_total=meter.create_counter(
            "ai_model_orchestration_engine_models_deregistered_total",
            description="Models deregistered from the Model Registry.",
        ),
        budget_exceeded_total=meter.create_counter(
            "ai_model_orchestration_engine_budget_exceeded_total",
            description="Budget threshold-exceeded events raised.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "ai_model_orchestration_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus, labeled by subject.",
        ),
    )

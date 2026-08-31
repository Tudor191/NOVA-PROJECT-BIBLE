"""Observability instruments (TDD 3C §9): the 4 named metrics, plus
`create_metrics()` following every other engine's own `observability.py`
convention. Must only be called after `configure_observability()` has run.
`domain/` never imports this module -- `main.py` reads the instruments off
`app.state.metrics`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram

__all__ = ["CapabilityEngineMetrics", "create_metrics"]


@dataclass(frozen=True)
class CapabilityEngineMetrics:
    install_pipeline_stage_total: Counter
    """Labeled by `stage` (one of the 8 `InstallationStage` values) and
    `outcome` -- TDD 3C §9's named metric, one counter per pipeline-stage
    transition."""

    sandbox_violation_blocked_total: Counter
    """Labeled by `adapter` -- the direct metric proving the roadmap's own
    acceptance bar (TDD 3C §9/§13): every blocked scope-escape attempt,
    whether from the install-time self-test or a runtime invocation."""

    invocation_total: Counter
    """Labeled by `adapter` and `outcome`
    (`success` | `failure` | `sandbox_violation`)."""

    invocation_duration_ms: Histogram
    """Latency of one `capability.invoke.*` call, labeled by `adapter`."""


def create_metrics() -> CapabilityEngineMetrics:
    meter = get_meter("capability-engine")
    return CapabilityEngineMetrics(
        install_pipeline_stage_total=meter.create_counter(
            "capability_install_pipeline_stage_total",
            description="Installation pipeline stage transitions, labeled by stage and outcome.",
        ),
        sandbox_violation_blocked_total=meter.create_counter(
            "capability_sandbox_violation_blocked_total",
            description="Blocked sandbox scope-escape attempts, labeled by adapter.",
        ),
        invocation_total=meter.create_counter(
            "capability_invocation_total",
            description="capability.invoke.* calls, labeled by adapter and outcome.",
        ),
        invocation_duration_ms=meter.create_histogram(
            "capability_invocation_duration_ms",
            description="Latency of one capability.invoke.* call, labeled by adapter.",
            unit="ms",
        ),
    )

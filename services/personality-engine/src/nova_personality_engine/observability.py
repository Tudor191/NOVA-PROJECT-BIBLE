"""Observability instruments -- docs/architecture/15-development-workflow.md
Sec9.0 item 10.

`create_metrics()` must only be called *after* `configure_observability()` has
run, mirroring every other engine's own `observability.py`. `api/` and
`events/` read the resulting instruments off `app.state.metrics`; `domain/`
never imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class PersonalityEngineMetrics:
    validate_response_duration_seconds: Histogram
    """Design doc Sec12: end-to-end latency of one `validate` call."""

    style_select_duration_seconds: Histogram
    """Design doc Sec12: end-to-end latency of one `select_style` call."""

    validations_total: Counter
    """Labeled by `outcome` (`passed` | `failed`, design doc Sec4/Sec8)."""

    violations_total: Counter
    """Labeled by `check_family` (design doc Sec4's four families)."""


def create_metrics() -> PersonalityEngineMetrics:
    meter = get_meter("personality-engine")
    return PersonalityEngineMetrics(
        validate_response_duration_seconds=meter.create_histogram(
            "personality_engine_validate_response_duration_seconds",
            description="End-to-end latency of one validate_response call.",
            unit="s",
        ),
        style_select_duration_seconds=meter.create_histogram(
            "personality_engine_style_select_duration_seconds",
            description="End-to-end latency of one style.select call.",
            unit="s",
        ),
        validations_total=meter.create_counter(
            "personality_engine_validations_total",
            description="Validation calls processed, labeled by outcome.",
        ),
        violations_total=meter.create_counter(
            "personality_engine_violations_total",
            description="Validator violations found, labeled by check_family.",
        ),
    )

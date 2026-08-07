"""Observability instruments -- docs/architecture/15-development-workflow.md
Sec9.0 item 10.

`create_metrics()` must only be called *after* `configure_observability()`
has run, mirroring every other engine's own `observability.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class PerceptionEngineMetrics:
    wake_phrase_request_duration_seconds: Histogram
    """Sec17's own performance goal (p95 < 300ms) -- the number that goal is
    checked against, per ADR-031."""

    identity_fusion_confidence: Histogram
    """Distribution of `IdentityConfidenceState.smoothed_confidence` -- Sec19's
    own drift signal: a healthy system should cluster at high/medium, not
    low/unknown."""

    identity_observations_total: Counter
    """Labeled by `confidence_tier`."""

    consent_grants_total: Counter
    consent_revocations_total: Counter

    sensor_health_checks_total: Counter
    """Labeled by `status` (`healthy` | `degraded` | `unhealthy`)."""

    sensor_restarts_total: Counter
    """Labeled by `sensor_id` -- Sec12's automatic-restart-on-failure path."""

    enrollments_total: Counter
    revocations_total: Counter

    outbox_dispatched_total: Counter
    """Labeled by `subject`."""


def create_metrics() -> PerceptionEngineMetrics:
    meter = get_meter("perception-engine")
    return PerceptionEngineMetrics(
        wake_phrase_request_duration_seconds=meter.create_histogram(
            "perception_engine_wake_phrase_request_duration_seconds",
            description="End-to-end latency of one detect_wake_phrase call.",
            unit="s",
        ),
        identity_fusion_confidence=meter.create_histogram(
            "perception_engine_identity_fusion_confidence",
            description="Distribution of smoothed identity confidence values.",
        ),
        identity_observations_total=meter.create_counter(
            "perception_engine_identity_observations_total",
            description="Fused identity observations recorded, labeled by confidence_tier.",
        ),
        consent_grants_total=meter.create_counter(
            "perception_engine_consent_grants_total",
            description="Consent grants recorded.",
        ),
        consent_revocations_total=meter.create_counter(
            "perception_engine_consent_revocations_total",
            description="Consent revocations recorded.",
        ),
        sensor_health_checks_total=meter.create_counter(
            "perception_engine_sensor_health_checks_total",
            description="Sensor health probes, labeled by resulting status.",
        ),
        sensor_restarts_total=meter.create_counter(
            "perception_engine_sensor_restarts_total",
            description=(
                "Automatic sensor restarts after a failed health check, labeled by sensor_id."
            ),
        ),
        enrollments_total=meter.create_counter(
            "perception_engine_enrollments_total",
            description="Identities enrolled into the Identity Registry.",
        ),
        revocations_total=meter.create_counter(
            "perception_engine_revocations_total",
            description="Identities revoked from the Identity Registry.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "perception_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus, labeled by subject.",
        ),
    )

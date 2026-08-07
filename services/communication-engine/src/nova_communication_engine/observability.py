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
class CommunicationEngineMetrics:
    intent_deliver_duration_seconds: Histogram
    """Design doc Sec13: end-to-end latency of one `deliver_intent` call."""

    intent_deliveries_total: Counter
    """Labeled by `outcome` (`delivered` | `rejected` | `undelivered`)."""

    personality_rpc_degraded_total: Counter
    """Design doc Sec9: count of `personality.validate_response` timeouts
    that triggered the deliver-unvalidated fallback."""

    barge_ins_total: Counter
    """Master Blueprint Sec13.4."""

    session_state_transitions_total: Counter
    """Labeled by `event` (design doc Sec3.1's `ConversationEvent` names)."""

    transcribe_failures_total: Counter
    synthesize_failures_total: Counter

    outbox_dispatched_total: Counter
    """Labeled by `subject`."""


def create_metrics() -> CommunicationEngineMetrics:
    meter = get_meter("communication-engine")
    return CommunicationEngineMetrics(
        intent_deliver_duration_seconds=meter.create_histogram(
            "communication_engine_intent_deliver_duration_seconds",
            description="End-to-end latency of one communication.intent.deliver call.",
            unit="s",
        ),
        intent_deliveries_total=meter.create_counter(
            "communication_engine_intent_deliveries_total",
            description="Intent gate outcomes, labeled by outcome.",
        ),
        personality_rpc_degraded_total=meter.create_counter(
            "communication_engine_personality_rpc_degraded_total",
            description="personality.validate_response timeouts that triggered the fallback.",
        ),
        barge_ins_total=meter.create_counter(
            "communication_engine_barge_ins_total",
            description="Barge-in interruptions detected while Speaking.",
        ),
        session_state_transitions_total=meter.create_counter(
            "communication_engine_session_state_transitions_total",
            description="ConversationSession state transitions, labeled by event.",
        ),
        transcribe_failures_total=meter.create_counter(
            "communication_engine_transcribe_failures_total",
            description="ai_model.transcribe calls that returned no result.",
        ),
        synthesize_failures_total=meter.create_counter(
            "communication_engine_synthesize_failures_total",
            description="ai_model.synthesize calls that returned no result.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "communication_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus, labeled by subject.",
        ),
    )

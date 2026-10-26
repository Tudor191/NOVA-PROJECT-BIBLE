"""Observability instruments for `cognitive-state-engine` (SAD 15 §9.1 item 10).

`create_metrics()` follows every other engine's `observability.py`
convention: it must only be called after `configure_observability()` has
run, and `domain/` never imports this module -- `events/handlers.py` receives
the instruments from `main.py`.

The engine's work arrives on two subscriptions, so its key rates are theirs:

* **sensor reports** (`perception.sensor.health_changed`) -- applied, ignored
  as duplicate or stale, or rejected;
* **workspace observations** (`perception.workspace.observed`) -- created,
  duplicate, foreign user, initiative lost, or rejected before ingestion;
* **initiative triggers** fired by a promotion, by the reply status
  `DecisionTriggerClient` reported;
* **ingestion latency**, which includes the trigger's bounded wait for
  `autonomy-engine`'s reply.

Every label is drawn from a closed set: the `Literal` types the domain already
declares, plus the handler's own rejection paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import get_args

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram

from nova_cognitive_state_engine.domain.ports import TriggerStatus
from nova_cognitive_state_engine.ingestion_orchestration import IngestionOutcome

__all__ = [
    "INGESTION_BUCKETS_SECONDS",
    "OBSERVATION_OUTCOMES",
    "SENSOR_REPORT_OUTCOMES",
    "TRIGGER_STATUSES",
    "CognitiveStateMetrics",
    "create_metrics",
]

#: `cognitive_state_sensor_reports_total`'s `outcome`.
SENSOR_REPORT_OUTCOMES: frozenset[str] = frozenset(
    {
        "applied",
        "ignored_duplicate_or_stale",
        "rejected_invalid_payload",
        "rejected_unknown_status",
        "not_stored",
    }
)

#: `cognitive_state_workspace_observations_total`'s `outcome`: every
#: `IngestionOutcome`, plus the two paths that end before one exists.
OBSERVATION_OUTCOMES: frozenset[str] = frozenset(
    set(get_args(IngestionOutcome)) | {"rejected_invalid_payload", "not_ingested"}
)

#: `cognitive_state_initiative_triggers_total`'s `status`.
TRIGGER_STATUSES: frozenset[str] = frozenset(get_args(TriggerStatus))

#: Seconds. An ingestion is a few statements, but one that promotes a thought
#: waits for `autonomy-engine`'s reply -- bounded at 20 s (4F.6 F-2) -- so the
#: buckets reach past that bound.
INGESTION_BUCKETS_SECONDS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    20.0,
    30.0,
)


@dataclass(frozen=True)
class CognitiveStateMetrics:
    sensor_reports_total: Counter
    """Labeled by `outcome`."""

    workspace_observations_total: Counter
    """Labeled by `outcome`. `initiative_lost` rising is FP-15's window."""

    initiative_triggers_total: Counter
    """Labeled by `status`: only promotions that fired a trigger count."""

    ingestion_duration_seconds: Histogram
    """One workspace observation, from receipt to done, labeled by `outcome`."""


def create_metrics() -> CognitiveStateMetrics:
    meter = get_meter("cognitive-state-engine")
    return CognitiveStateMetrics(
        sensor_reports_total=meter.create_counter(
            "cognitive_state_sensor_reports_total",
            description="Sensor health reports, labeled by outcome.",
        ),
        workspace_observations_total=meter.create_counter(
            "cognitive_state_workspace_observations_total",
            description="Workspace observations, labeled by ingestion outcome.",
        ),
        initiative_triggers_total=meter.create_counter(
            "cognitive_state_initiative_triggers_total",
            description="Initiative triggers fired by a promotion, labeled by reply status.",
        ),
        ingestion_duration_seconds=meter.create_histogram(
            "cognitive_state_ingestion_duration_seconds",
            unit="s",
            description="Time to ingest one workspace observation, labeled by outcome.",
            explicit_bucket_boundaries_advisory=INGESTION_BUCKETS_SECONDS,
        ),
    )

"""Observability instruments for `autonomy-engine` (SAD 15 §9.1 item 10).

`create_metrics()` follows every other engine's `observability.py`
convention: it must only be called after `configure_observability()` has
run, and `domain/` never imports this module -- the API layer and the
decision-trigger adapter read the instruments off `app.state.metrics`.

Three things an operator needs to see, each as a bounded-label instrument:

* **what the engine decided**, from the initiative trigger and from the
  suggestion inbox -- `autonomy_decisions_total`;
* **how long a triggered decision took**, including the Level-2 dispatch
  wait -- `autonomy_decision_duration_seconds`;
* **when its own authority was reconfigured** -- the level, a policy, or the
  permission matrix -- `autonomy_configuration_changes_total`. These are the
  changes that can make an action execute without approval, so they are
  counted as well as logged (`api/autonomy.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram

from nova_autonomy_engine.domain.models import DecisionOutcome

__all__ = [
    "CONFIGURATION_KINDS",
    "DECISION_OUTCOMES",
    "DECISION_SOURCES",
    "DURATION_BUCKETS_SECONDS",
    "AutonomyMetrics",
    "create_metrics",
]

#: `autonomy_decisions_total`'s `source`.
DECISION_SOURCES: frozenset[str] = frozenset({"trigger", "suggestion_inbox"})

#: `autonomy_decisions_total`'s `outcome`: every `DecisionOutcome`, plus the
#: two trigger replies that are not a decision -- a request refused at
#: contract validation (`rejected`) and one that could not be decided or
#: recorded (`degraded`).
DECISION_OUTCOMES: frozenset[str] = frozenset(
    {outcome.value for outcome in DecisionOutcome} | {"rejected", "degraded"}
)

#: `autonomy_configuration_changes_total`'s `kind` (`operation` is one of
#: `set`, `create`, `update`, `delete`).
CONFIGURATION_KINDS: frozenset[str] = frozenset({"level", "policy", "permissions"})

#: Seconds. A triggered decision is a few queries and, at Level 2, one
#: `action.execute` round trip bounded at 15 s (D-4F5-3), so the buckets
#: reach past that bound.
DURATION_BUCKETS_SECONDS: tuple[float, ...] = (
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
    15.0,
    20.0,
    30.0,
)


@dataclass(frozen=True)
class AutonomyMetrics:
    decisions_total: Counter
    """Labeled by `source` and `outcome`."""

    decision_duration_seconds: Histogram
    """A triggered decision, from receipt to reply, labeled by `outcome`."""

    configuration_changes_total: Counter
    """Labeled by `kind` and `operation`."""


def create_metrics() -> AutonomyMetrics:
    meter = get_meter("autonomy-engine")
    return AutonomyMetrics(
        decisions_total=meter.create_counter(
            "autonomy_decisions_total",
            description="Autonomy decisions, labeled by source and outcome.",
        ),
        decision_duration_seconds=meter.create_histogram(
            "autonomy_decision_duration_seconds",
            unit="s",
            description="Time to answer a triggered decision, labeled by outcome.",
            explicit_bucket_boundaries_advisory=DURATION_BUCKETS_SECONDS,
        ),
        configuration_changes_total=meter.create_counter(
            "autonomy_configuration_changes_total",
            description="Changes to the level, a policy or the permission matrix.",
        ),
    )

"""Observability instruments (TDD 3B §9's `planning_*` naming convention,
adapted to this PR's actual scope -- no persistence exists yet, so nothing
here claims a `TaskGraph` was durably "created"; that is the persistence
PR's own metric to add). Mirrors `reasoning-engine`'s own
`observability.py`: a small, labeled instrument set rather than one
counter per lifecycle point, the same "increment once, label by outcome"
economy `reasoning_requests_total` already establishes.

`create_metrics()` must only be called after `configure_observability()`
has run, mirroring every other engine's own `observability.py`. `domain/`
never imports this module -- `events/handlers.py` reads the instruments
off `app.state.metrics`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram

__all__ = ["PlanningEngineMetrics", "create_metrics"]


@dataclass(frozen=True)
class PlanningEngineMetrics:
    reasoning_completions_received_total: Counter
    """Every `reasoning.process.completed` event this engine's handler
    received, regardless of what happened next -- the "event received"
    lifecycle point Part 15 requires distinguishing."""

    decomposition_attempts_total: Counter
    """Labeled by `outcome` (`below_threshold` | `succeeded` | `failed`);
    `failed` attempts are additionally labeled by `reason`
    (`DecompositionError.reason`, e.g. `model_timeout`, `model_error`,
    `no_structured_output`, `malformed_task_fields`, `cycle`,
    `dangling_dependencies`). Jointly covers "decomposition requested",
    "model generation succeeded/failed", and "graph validation
    succeeded/failed" as one instrument's label dimensions, the same
    economy `reasoning_requests_total` already establishes."""

    decomposition_duration_seconds: Histogram
    """Latency of one `decompose()` call, labeled by `outcome`."""

    decomposition_task_count: Histogram
    """Number of `TaskNode`s in a successfully decomposed `TaskGraph`."""


def create_metrics() -> PlanningEngineMetrics:
    meter = get_meter("planning-engine")
    return PlanningEngineMetrics(
        reasoning_completions_received_total=meter.create_counter(
            "planning_engine_reasoning_completions_received_total",
            description="reasoning.process.completed events received by this engine.",
        ),
        decomposition_attempts_total=meter.create_counter(
            "planning_engine_decomposition_attempts_total",
            description="Decomposition attempts, labeled by outcome (and reason when failed).",
        ),
        decomposition_duration_seconds=meter.create_histogram(
            "planning_engine_decomposition_duration_seconds",
            description="Latency of a decompose() call, labeled by outcome.",
            unit="s",
        ),
        decomposition_task_count=meter.create_histogram(
            "planning_engine_decomposition_task_count",
            description="Number of TaskNodes produced by a successful decomposition.",
        ),
    )

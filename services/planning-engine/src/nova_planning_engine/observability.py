"""Observability instruments (TDD 3B §9's `planning_*` naming convention).
Mirrors `reasoning-engine`'s own `observability.py`: a small, labeled
instrument set rather than one counter per lifecycle point, the same
"increment once, label by outcome" economy `reasoning_requests_total`
already establishes.

**`phase-3b-planning-persistence` precursor, additive:** the four
TDD 3B §9-named instruments this engine's persistence/publication/
decompose-request scope requires (`planning_task_graph_created_total`,
`planning_task_graph_mutated_total`,
`planning_decompose_request_served_total`,
`planning_decompose_request_already_minimal_total`,
`planning_critical_path_length`) -- deferred from the original
decomposition-orchestration unit, whose own module docstring correctly
disclosed "no persistence exists yet, so nothing here claims a `TaskGraph`
was durably 'created'."

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

    planning_task_graph_created_total: Counter
    """TDD 3B §9: one increment per `TaskGraph` durably persisted via
    `reasoning.process.completed` -> `decompose()`."""

    planning_task_graph_mutated_total: Counter
    """One increment per `PlanningRepository.append_nodes` call that
    succeeds (the `planning.decompose.request` mutation path)."""

    planning_decompose_request_served_total: Counter
    """Every `planning.decompose.request` this engine serves, labeled by
    `already_minimal` (`"true"`/`"false"`)."""

    planning_decompose_request_already_minimal_total: Counter
    """TDD 3B §9's own named "already minimal" counter -- a subset of
    `planning_decompose_request_served_total`, kept as its own instrument
    since TDD 3B §9 names both explicitly."""

    planning_critical_path_length: Histogram
    """`len(TaskGraph.critical_path)`, per graph, at creation and at every
    mutation."""

    outbox_dispatched_total: Counter
    """Outbox events dispatched to the Event Bus by
    `repository/outbox_dispatcher.py` (`workers/outbox_worker.py`) --
    mirrors `memory-engine`'s own instrument of the same name."""


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
        planning_task_graph_created_total=meter.create_counter(
            "planning_task_graph_created_total",
            description="TaskGraphs durably persisted (reasoning.process.completed path).",
        ),
        planning_task_graph_mutated_total=meter.create_counter(
            "planning_task_graph_mutated_total",
            description="TaskGraphs mutated in place (planning.decompose.request path).",
        ),
        planning_decompose_request_served_total=meter.create_counter(
            "planning_decompose_request_served_total",
            description="planning.decompose.request calls served, labeled by already_minimal.",
        ),
        planning_decompose_request_already_minimal_total=meter.create_counter(
            "planning_decompose_request_already_minimal_total",
            description="planning.decompose.request calls where the model proposed no "
            "further breakdown.",
        ),
        planning_critical_path_length=meter.create_histogram(
            "planning_critical_path_length",
            description="len(TaskGraph.critical_path), per graph, at creation and mutation.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "planning_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus.",
        ),
    )

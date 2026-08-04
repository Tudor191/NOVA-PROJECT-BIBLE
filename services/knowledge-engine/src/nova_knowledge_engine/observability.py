"""Observability instruments -- docs/architecture/15-development-workflow.md §9
item 10 (write/read latency, failure rate, and similar signals a future on-call
engineer would actually need).

`create_metrics()` must only be called *after* `configure_observability()` has run
(OTel's global `MeterProvider` must already be the real one, not the no-op
default it starts as) -- mirroring `nova-core`'s `HeartbeatPublisher` and Memory
Engine's `observability.py`, both constructed inside `create_app()` after
`configure_observability()`, never at module import time. `api/` and `workers/`
read the resulting instruments off `app.state.metrics` / a passed-in
`KnowledgeEngineMetrics`; `domain/` never imports this module -- metrics are a
concern of the edges, not of pure business logic (docs/architecture/
03-backend-architecture.md §1's framework-free rule, extended).
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class KnowledgeEngineMetrics:
    acquisition_duration_seconds: Histogram
    """Latency of `domain.acquisition.ingest`'s full pipeline (normalize ->
    validate -> check_for_conflicts -> write)."""

    retrieval_duration_seconds: Histogram
    """Latency of a full `retrieve()` call (semantic + graph + name fan-out)."""

    nodes_acquired_total: Counter
    """Labeled by `outcome` (`created` | `corroborated` | `conflict`)."""

    retrieval_degraded_total: Counter
    """Retrievals where `VectorIndex` or `GraphStore` was unreachable and results
    fell back to a narrower search mode (docs/design/phase-1/
    02-knowledge-engine.md §17)."""

    contradictions_detected_total: Counter

    layer_advances_total: Counter
    """Labeled by `to_layer`."""

    embeddings_total: Counter
    """Nodes embedded by `workers/embedding_worker.py`."""

    graph_writes_applied_total: Counter
    """Neo4j writes applied by the saga dispatcher's step 2 (§17)."""

    outbox_dispatched_total: Counter
    """Outbox events dispatched to the Event Bus by the saga dispatcher's step 3."""

    graph_write_degraded_total: Counter
    """Outbox rows found still pending their Neo4j write past
    `Settings.graph_write_degraded_threshold_minutes` -- the operational signal
    §17 step 4 calls for (a Prometheus metric + log, not a bus event)."""


def create_metrics() -> KnowledgeEngineMetrics:
    meter = get_meter("knowledge-engine")
    return KnowledgeEngineMetrics(
        acquisition_duration_seconds=meter.create_histogram(
            "knowledge_engine_acquisition_duration_seconds",
            description="Latency of the acquisition pipeline.",
            unit="s",
        ),
        retrieval_duration_seconds=meter.create_histogram(
            "knowledge_engine_retrieval_duration_seconds",
            description="Latency of a full retrieve() call.",
            unit="s",
        ),
        nodes_acquired_total=meter.create_counter(
            "knowledge_engine_nodes_acquired_total",
            description="Acquisition outcomes, labeled by outcome.",
        ),
        retrieval_degraded_total=meter.create_counter(
            "knowledge_engine_retrieval_degraded_total",
            description="Retrievals that degraded due to VectorIndex/GraphStore unavailability.",
        ),
        contradictions_detected_total=meter.create_counter(
            "knowledge_engine_contradictions_detected_total",
            description="Structural contradictions detected by domain.contradiction.",
        ),
        layer_advances_total=meter.create_counter(
            "knowledge_engine_layer_advances_total",
            description="Knowledge layer advances, labeled by to_layer.",
        ),
        embeddings_total=meter.create_counter(
            "knowledge_engine_embeddings_total",
            description="Nodes embedded by embedding_worker.",
        ),
        graph_writes_applied_total=meter.create_counter(
            "knowledge_engine_graph_writes_applied_total",
            description="Neo4j writes applied by the saga dispatcher.",
        ),
        outbox_dispatched_total=meter.create_counter(
            "knowledge_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus, labeled by subject.",
        ),
        graph_write_degraded_total=meter.create_counter(
            "knowledge_engine_graph_write_degraded_total",
            description="Outbox rows stuck pending a Neo4j write past the degraded threshold.",
        ),
    )

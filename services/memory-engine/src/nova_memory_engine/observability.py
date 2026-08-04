"""Observability instruments -- docs/architecture/15-development-workflow.md §9
item 10 (write/read latency, failure rate, and similar signals a future on-call
engineer would actually need).

`create_metrics()` must only be called *after* `configure_observability()` has run
(OTel's global `MeterProvider` must already be the real one, not the no-op
default it starts as) -- mirroring `nova-core`'s `HeartbeatPublisher`, which is
likewise constructed inside `create_app()` after `configure_observability()`, never
at module import time. `api/` and `workers/` read the resulting instruments off
`app.state.metrics` / a passed-in `MemoryEngineMetrics`; `domain/` never imports
this module -- metrics are a concern of the edges, not of pure business logic
(docs/architecture/03-backend-architecture.md §1's framework-free rule, extended).
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram


@dataclass(frozen=True)
class MemoryEngineMetrics:
    write_duration_seconds: Histogram
    """Latency of a long-term or short-term memory write, excluding async
    embedding (which is deliberately off this path -- docs/design/phase-1/
    01-memory-engine.md §10)."""

    retrieval_duration_seconds: Histogram
    """Latency of a full `retrieve()` call (semantic + timeline + optional
    relationship fan-out)."""

    writes_total: Counter
    """Labeled by `memory_type`."""

    retrieval_degraded_total: Counter
    """Retrievals that fell back to timeline-only results because `VectorIndex`
    was unreachable (docs/design/phase-1/01-memory-engine.md §17)."""

    consolidation_records_total: Counter
    """Labeled by `outcome` (`merged` | `advanced` | `deleted`)."""

    embeddings_total: Counter
    """Memories embedded by `workers/embedding_worker.py`."""

    outbox_dispatched_total: Counter
    """Outbox events dispatched to the Event Bus by `repository/outbox_dispatcher.py`."""


def create_metrics() -> MemoryEngineMetrics:
    meter = get_meter("memory-engine")
    return MemoryEngineMetrics(
        write_duration_seconds=meter.create_histogram(
            "memory_engine_write_duration_seconds",
            description="Latency of a memory write, excluding async embedding.",
            unit="s",
        ),
        retrieval_duration_seconds=meter.create_histogram(
            "memory_engine_retrieval_duration_seconds",
            description="Latency of a full retrieve() call.",
            unit="s",
        ),
        writes_total=meter.create_counter(
            "memory_engine_writes_total", description="Memory writes, labeled by memory_type."
        ),
        retrieval_degraded_total=meter.create_counter(
            "memory_engine_retrieval_degraded_total",
            description="Retrievals that degraded due to VectorIndex unavailability.",
        ),
        consolidation_records_total=meter.create_counter(
            "memory_engine_consolidation_records_total",
            description="Records affected by a consolidation run, labeled by outcome.",
        ),
        embeddings_total=meter.create_counter(
            "memory_engine_embeddings_total", description="Memories embedded by embedding_worker."
        ),
        outbox_dispatched_total=meter.create_counter(
            "memory_engine_outbox_dispatched_total",
            description="Outbox events dispatched to the Event Bus.",
        ),
    )

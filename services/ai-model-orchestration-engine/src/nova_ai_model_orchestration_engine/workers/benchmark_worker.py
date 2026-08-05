"""Benchmark worker -- Part 7 "Model Benchmarking": periodically runs the same
small, fixed evaluation set `domain/benchmark.py` defines against every
registered, healthy model, feeding the result back into `avg_latency_ms`/
`avg_quality_score` (design doc §2, §7's "Store Experience / Improve Future
Routing"). Runs on `Settings.benchmark_interval_hours`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_observability import get_logger

from nova_ai_model_orchestration_engine.connectors.factory import (
    ConnectorFactory,
    ConnectorUnavailableError,
)
from nova_ai_model_orchestration_engine.domain import benchmark as benchmark_domain
from nova_ai_model_orchestration_engine.domain.ports import ModelRegistryRepository

if TYPE_CHECKING:
    from nova_ai_model_orchestration_engine.observability import AiModelOrchestrationEngineMetrics

logger = get_logger("ai-model-orchestration-engine.workers.benchmark")


async def run_benchmarks(
    repository: ModelRegistryRepository,
    connector_factory: ConnectorFactory,
    *,
    metrics: AiModelOrchestrationEngineMetrics | None = None,
) -> int:
    """Returns the number of models benchmarked. Only `healthy` models are
    benchmarked -- an unreachable connector has nothing useful to measure
    beyond what `health_monitor_worker.py` already tracks."""
    models = await repository.list_all(health_status="healthy")
    benchmarked = 0
    for model in models:
        try:
            connector = connector_factory.get_connector(model)
        except ConnectorUnavailableError:
            continue
        result = await benchmark_domain.run_benchmark(connector)
        await repository.update_benchmark(
            model.id,
            avg_latency_ms=result.avg_latency_ms,
            avg_quality_score=result.avg_quality_score,
        )
        benchmarked += 1
        if metrics is not None:
            metrics.benchmark_runs_total.add(1)
    if benchmarked:
        logger.info("benchmark cycle complete", extra={"benchmarked": benchmarked})
    return benchmarked


async def arq_run_benchmarks(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_benchmarks(
        ctx["registry_repository"], ctx["connector_factory"], metrics=ctx.get("metrics")
    )

"""Health monitor worker -- Part 7 "Model Health": periodically probes every
registered connector's availability/latency and writes a health snapshot,
demoting unhealthy models' routing priority (design doc §2, §6). Runs on
`Settings.health_check_interval_seconds`, the same fixed-poll tradeoff every
Phase 1 worker accepts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nova_observability import get_logger

from nova_ai_model_orchestration_engine.connectors.factory import (
    ConnectorFactory,
    ConnectorUnavailableError,
)
from nova_ai_model_orchestration_engine.domain.health import compute_health_status
from nova_ai_model_orchestration_engine.domain.models import ConnectorHealth
from nova_ai_model_orchestration_engine.domain.ports import ModelConnector, ModelRegistryRepository

if TYPE_CHECKING:
    from nova_ai_model_orchestration_engine.observability import AiModelOrchestrationEngineMetrics

logger = get_logger("ai-model-orchestration-engine.workers.health_monitor")


async def _probe(connector: ModelConnector) -> ConnectorHealth:
    try:
        return await connector.health()
    except Exception:  # noqa: BLE001 -- an unreachable connector is a status, not a crash
        return ConnectorHealth(available=False)


async def run_health_checks(
    repository: ModelRegistryRepository,
    connector_factory: ConnectorFactory,
    *,
    metrics: AiModelOrchestrationEngineMetrics | None = None,
) -> int:
    """Returns the number of models probed."""
    models = await repository.list_all()
    checked = 0
    for model in models:
        try:
            connector = connector_factory.get_connector(model)
        except ConnectorUnavailableError:
            continue
        snapshot = await _probe(connector)
        status = compute_health_status(snapshot)
        await repository.update_health(model.id, status=status, snapshot=snapshot)
        checked += 1
        if metrics is not None:
            metrics.health_checks_total.add(1, {"status": status})
    return checked


async def arq_run_health_checks(ctx: dict) -> None:
    """Arq entrypoint (`WorkerSettings.cron_jobs` in `workers/__init__.py`)."""
    await run_health_checks(
        ctx["registry_repository"], ctx["connector_factory"], metrics=ctx.get("metrics")
    )

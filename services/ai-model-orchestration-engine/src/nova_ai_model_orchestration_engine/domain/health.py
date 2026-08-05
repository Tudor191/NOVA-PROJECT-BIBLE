"""Model health status computation from a single connector health snapshot
(Bible Part 7 "Model Health"; docs/design/phase-2a/00-ai-model-orchestration-engine.md
§2, §6). Pure thresholding over one probe's result -- no trend/history analysis
in Phase 2A, `workers/health_monitor_worker.py` calls this on every probe and
persists whatever it returns; this module never touches the repository itself.
"""

from __future__ import annotations

from nova_ai_model_orchestration_engine.domain.models import ConnectorHealth, HealthStatus

__all__ = ["DEGRADED_ERROR_RATE_THRESHOLD", "compute_health_status"]

DEGRADED_ERROR_RATE_THRESHOLD = 0.1
"""Above this error rate, a reachable connector is `degraded`, not `healthy` --
Part 7 gives no exact number; one in ten recent requests failing is treated as a
real signal, not noise, the same "honest, not invented precision" standard as
`router.py`'s complexity heuristic."""


def compute_health_status(snapshot: ConnectorHealth) -> HealthStatus:
    """§6's state machine: `unhealthy` when the connector itself reports
    unreachable, `degraded` when reachable but error-prone, `healthy` otherwise."""
    if not snapshot.available:
        return "unhealthy"
    if snapshot.error_rate is not None and snapshot.error_rate > DEGRADED_ERROR_RATE_THRESHOLD:
        return "degraded"
    return "healthy"

"""nova-service-kit: shared FastAPI/SQLAlchemy infrastructure boilerplate --
health/readiness routing, Postgres engine/session-factory construction, the
transactional-outbox dispatch loop, and the per-service arq worker identity
that keeps one engine's scheduled jobs out of another's worker -- used
identically by every engine that has one, with zero engine-specific knowledge
of any kind (ADR-034).

See `docs/design/nova-service-kit/boilerplate-extraction-proposal.md` for the
extraction rationale and `docs/architecture/adr/
ADR-034-shared-infrastructure-packages-carry-zero-engine-specific-knowledge.md`
for the permanent boundary rule this package is built to.
"""

from nova_service_kit.db import create_engine, create_session_factory
from nova_service_kit.health import make_health_router
from nova_service_kit.outbox import (
    OutboxMetrics,
    OutboxRepository,
    OutboxRow,
    dispatch_ready_events,
)
from nova_service_kit.worker import (
    CRON_NAME_PREFIX,
    QUEUE_NAME_PREFIX,
    cron_job_name,
    service_cron,
    worker_queue_name,
)

__all__ = [
    "CRON_NAME_PREFIX",
    "QUEUE_NAME_PREFIX",
    "OutboxMetrics",
    "OutboxRepository",
    "OutboxRow",
    "create_engine",
    "create_session_factory",
    "cron_job_name",
    "dispatch_ready_events",
    "make_health_router",
    "service_cron",
    "worker_queue_name",
]

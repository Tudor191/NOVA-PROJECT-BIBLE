"""`/internal/health` and `/internal/readiness` -- and **negative control 12**
at the probe: a degraded database must not report ready."""

from __future__ import annotations

from fastapi.testclient import TestClient
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.main import create_app

from tests.fakes.repository import FakeAutonomyRepository


def test_health_and_readiness(client: TestClient) -> None:
    health = client.get("/internal/health")
    readiness = client.get("/internal/readiness")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True


def test_readiness_reports_not_ready_when_the_database_is_unreachable(
    settings: Settings,
) -> None:
    """**Negative control 12**, at the readiness probe. A readiness endpoint
    that only echoes a startup flag reports a degraded service as healthy."""
    repository = FakeAutonomyRepository()
    repository.healthy = False
    app = create_app(settings, repository=repository)
    with TestClient(app) as degraded:
        response = degraded.get("/internal/readiness")

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert "unreachable" in response.json()["detail"]


def test_liveness_does_not_depend_on_the_database(settings: Settings) -> None:
    """A database outage must not restart the process."""
    repository = FakeAutonomyRepository()
    repository.healthy = False
    app = create_app(settings, repository=repository)
    with TestClient(app) as degraded:
        assert degraded.get("/internal/health").json()["status"] == "healthy"

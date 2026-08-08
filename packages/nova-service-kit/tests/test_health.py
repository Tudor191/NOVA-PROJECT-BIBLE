from fastapi import FastAPI
from fastapi.testclient import TestClient
from nova_service_kit.health import make_health_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(make_health_router())
    return TestClient(app)


def test_health_reports_healthy() -> None:
    with _client() as client:
        response = client.get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_defaults_to_false_when_app_state_has_no_ready_attribute() -> None:
    with _client() as client:
        response = client.get("/internal/readiness")

    assert response.status_code == 200
    assert response.json() == {"ready": False}


def test_readiness_reflects_app_state_ready() -> None:
    app = FastAPI()
    app.include_router(make_health_router())
    app.state.ready = True

    with TestClient(app) as client:
        response = client.get("/internal/readiness")

    assert response.json() == {"ready": True}

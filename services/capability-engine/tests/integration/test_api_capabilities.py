"""End-to-end tests through `api/capabilities.py` -- `create_app()`'s
lifespan bootstrap-installs the four built-ins for real against
`FakeCapabilityRepository` and the engine's own real adapters (cheap and
side-effect-free at install time -- the self-test probe is always blocked
before any subprocess/network I/O happens, see `domain/pipeline.py`'s own
`_out_of_scope_probe`), then this file exercises `GET`/`POST /install`/
`DELETE` through a real `TestClient`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from nova_capability_engine.config import Settings
from nova_capability_engine.main import create_app

from tests.fakes.repository import FakeCapabilityRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeCapabilityRepository()
    app = create_app(Settings(), repository=repository)
    with TestClient(app) as client:
        yield client, repository


def test_the_four_built_ins_are_installed_at_startup(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    response = client.get("/v1/capabilities")

    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert names == {"filesystem", "terminal", "git", "http"}
    assert all(c["health_status"] == "healthy" for c in response.json())


def test_install_is_idempotent_on_repeated_requests(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    manifest = {
        "name": "custom-tool",
        "description": "a custom test capability",
        "category": "test",
        "version": "1.0.0",
        "required_permissions": [],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "filesystem",
    }

    first = client.post("/v1/capabilities/install", json=manifest)
    second = client.post("/v1/capabilities/install", json=manifest)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert sum(1 for c in repository.capabilities.values() if c.name == "custom-tool") == 1


def test_install_with_a_missing_dependency_returns_422(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness
    manifest = {
        "name": "depends-on-nothing-real",
        "description": "x",
        "category": "test",
        "version": "1.0.0",
        "dependencies": ["nonexistent-capability"],
        "required_permissions": [],
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "execution_adapter": "filesystem",
    }

    response = client.post("/v1/capabilities/install", json=manifest)

    assert response.status_code == 422


def test_delete_removes_an_installed_capability(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness
    capability_id = client.get("/v1/capabilities").json()[0]["id"]

    delete_response = client.delete(f"/v1/capabilities/{capability_id}")
    assert delete_response.status_code == 204

    remaining_ids = {c["id"] for c in client.get("/v1/capabilities").json()}
    assert capability_id not in remaining_ids


def test_delete_a_nonexistent_capability_returns_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness
    from uuid import uuid4

    response = client.delete(f"/v1/capabilities/{uuid4()}")

    assert response.status_code == 404

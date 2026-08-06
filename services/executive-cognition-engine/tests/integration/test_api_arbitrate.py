"""End-to-end tests through `api/arbitrate.py` -- exercises
`domain.coordinate.arbitrate_request` against in-memory fakes for `GoalsPort`
and `ExecutiveRepository`, injected via `create_app`'s constructor overrides
(no real Postgres/Event Bus RPC involved).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_executive_cognition_engine.config import Settings
from nova_executive_cognition_engine.main import create_app

from tests.fakes.ports import FakeGoalsPort
from tests.fakes.repository import FakeExecutiveRepository


def _payload(**overrides: object) -> dict:
    body = dict(
        requesting_engine="reasoning-engine",
        request_kind="reasoning_process",
        user_id=str(uuid4()),
        urgency=0.5,
        importance=0.5,
        complexity=0.5,
        risk=0.5,
        learning_value=0.5,
        resource_cost=0.5,
        user_impact=0.5,
    )
    body.update(overrides)
    return body


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeExecutiveRepository()
    app = create_app(Settings(), goals_port=FakeGoalsPort(), repository=repository)
    with TestClient(app) as client:
        yield client, repository


def test_arbitrate_endpoint_returns_a_proceed_reply_for_a_lone_request(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    response = client.post("/v1/executive/arbitrate", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "proceed"
    assert body["priority_score"]["composite"] > 0.0
    assert repository.decisions  # the handler actually ran arbitrate_request


def test_arbitrate_endpoint_rejects_out_of_bounds_priority_factors(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.post("/v1/executive/arbitrate", json=_payload(urgency=1.5))
    assert response.status_code == 422


def test_arbitrate_endpoint_requires_user_id(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    body = _payload()
    del body["user_id"]
    response = client.post("/v1/executive/arbitrate", json=body)
    assert response.status_code == 422


def test_second_concurrent_request_is_ranked_against_the_first(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    first = client.post(
        "/v1/executive/arbitrate",
        json=_payload(urgency=0.9, importance=0.9, resource_cost=1.0),
    )
    second = client.post(
        "/v1/executive/arbitrate",
        json=_payload(
            requesting_engine="ai-model-orchestration-engine",
            request_kind="model_generate",
            urgency=0.1,
            importance=0.1,
            resource_cost=1.0,
        ),
    )
    assert first.json()["outcome"] == "proceed"
    assert second.json()["outcome"] == "wait"

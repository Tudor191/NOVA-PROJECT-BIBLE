"""End-to-end tests through `api/decisions.py` -- list/get/explain/override,
against in-memory fakes (no real Postgres/Event Bus RPC involved).
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


def test_get_decision_returns_404_when_missing(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.get(f"/v1/executive/decisions/{uuid4()}")
    assert response.status_code == 404


def test_get_and_explain_return_the_same_trace(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    arbitrate_response = client.post("/v1/executive/arbitrate", json=_payload())
    decision_id = arbitrate_response.json()["executive_decision_id"]

    get_response = client.get(f"/v1/executive/decisions/{decision_id}")
    explain_response = client.get(f"/v1/executive/decisions/{decision_id}/explain")
    assert get_response.status_code == 200
    assert explain_response.status_code == 200
    assert get_response.json() == explain_response.json()


def test_list_decisions_filters_by_requesting_engine(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    client.post("/v1/executive/arbitrate", json=_payload(requesting_engine="reasoning-engine"))
    client.post(
        "/v1/executive/arbitrate",
        json=_payload(requesting_engine="ai-model-orchestration-engine"),
    )

    all_decisions = client.get("/v1/executive/decisions")
    filtered = client.get(
        "/v1/executive/decisions", params={"requesting_engine": "reasoning-engine"}
    )
    assert len(all_decisions.json()) == 2
    assert len(filtered.json()) == 1


def test_override_redirect_changes_the_recorded_outcome(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    arbitrate_response = client.post("/v1/executive/arbitrate", json=_payload())
    decision_id = arbitrate_response.json()["executive_decision_id"]
    assert arbitrate_response.json()["outcome"] == "proceed"

    override_response = client.post(
        f"/v1/executive/decisions/{decision_id}/override",
        json={
            "executive_decision_id": decision_id,
            "action": "redirect",
            "redirect_outcome": "wait",
        },
    )
    assert override_response.status_code == 200
    assert override_response.json()["outcome"] == "wait"
    assert override_response.json()["human_override"]["action"] == "redirect"


def test_override_redirect_without_redirect_outcome_is_rejected(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    arbitrate_response = client.post("/v1/executive/arbitrate", json=_payload())
    decision_id = arbitrate_response.json()["executive_decision_id"]

    override_response = client.post(
        f"/v1/executive/decisions/{decision_id}/override",
        json={"executive_decision_id": decision_id, "action": "redirect"},
    )
    assert override_response.status_code == 400


def test_override_confirm_leaves_the_outcome_unchanged(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    arbitrate_response = client.post("/v1/executive/arbitrate", json=_payload())
    decision_id = arbitrate_response.json()["executive_decision_id"]

    override_response = client.post(
        f"/v1/executive/decisions/{decision_id}/override",
        json={"executive_decision_id": decision_id, "action": "confirm"},
    )
    assert override_response.status_code == 200
    assert override_response.json()["outcome"] == "proceed"


def test_override_on_unknown_decision_returns_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    decision_id = str(uuid4())
    override_response = client.post(
        f"/v1/executive/decisions/{decision_id}/override",
        json={"executive_decision_id": decision_id, "action": "confirm"},
    )
    assert override_response.status_code == 404

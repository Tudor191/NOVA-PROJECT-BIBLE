"""End-to-end tests through `api/reason.py` -- exercises `domain/pipeline.py`
against in-memory fakes for every port and the repository, injected via
`create_app`'s constructor overrides (no real Postgres/Event Bus RPC
involved).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_reasoning_engine.config import Settings
from nova_reasoning_engine.domain.models import KnowledgeReference
from nova_reasoning_engine.main import create_app

from tests.fakes.ports import (
    FakeGoalsPort,
    FakeKnowledgePort,
    FakeMemoryPort,
    FakeModelOrchestrationPort,
    FakePersonalContextPort,
    FakeWorldModelPort,
)
from tests.fakes.repository import FakeReasoningRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    knowledge_port = FakeKnowledgePort(
        [KnowledgeReference(node_id="n1", name="Paris", layer="verified", confidence=0.9)]
    )
    repository = FakeReasoningRepository()
    app = create_app(
        Settings(),
        memory_port=FakeMemoryPort(),
        knowledge_port=knowledge_port,
        world_model_port=FakeWorldModelPort(),
        personal_context_port=FakePersonalContextPort(),
        goals_port=FakeGoalsPort(),
        model_orchestration_port=FakeModelOrchestrationPort(),
        repository=repository,
    )
    with TestClient(app) as client:
        yield client, repository


def test_reason_endpoint_returns_a_decided_reactive_reply(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness

    response = client.post(
        "/v1/reasoning/reason",
        json={
            "objective_text": "what is the capital of France?",
            "user_id": str(uuid4()),
            "requesting_engine": "test",
            "reasoning_mode_hint": "reactive",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "decided"
    assert body["confidence_score"] == pytest.approx(0.9)
    assert body["chosen_description"] == "Paris"
    assert repository.decisions  # persisted


def test_reason_endpoint_rejects_collaborative_mode(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    response = client.post(
        "/v1/reasoning/reason",
        json={
            "objective_text": "anything",
            "user_id": str(uuid4()),
            "requesting_engine": "test",
            "reasoning_mode_hint": "collaborative",
        },
    )

    assert response.status_code == 501


def test_traces_and_decisions_endpoints_round_trip(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    reason_response = client.post(
        "/v1/reasoning/reason",
        json={
            "objective_text": "what is the capital of France?",
            "user_id": str(uuid4()),
            "requesting_engine": "test",
            "reasoning_mode_hint": "reactive",
        },
    )
    trace_id = reason_response.json()["trace_id"]
    decision_id = reason_response.json()["decision_id"]

    trace_response = client.get(f"/v1/reasoning/traces/{trace_id}")
    assert trace_response.status_code == 200
    assert trace_response.json()["id"] == trace_id

    decision_response = client.get(f"/v1/reasoning/decisions/{decision_id}")
    assert decision_response.status_code == 200

    explain_response = client.get(f"/v1/reasoning/decisions/{decision_id}/explain")
    assert explain_response.status_code == 200
    assert "chosen_reason" in explain_response.json()

    list_response = client.get("/v1/reasoning/traces")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_missing_trace_and_decision_return_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    assert client.get(f"/v1/reasoning/traces/{uuid4()}").status_code == 404
    assert client.get(f"/v1/reasoning/decisions/{uuid4()}").status_code == 404


def _reason(client, user_id) -> dict:  # type: ignore[no-untyped-def]
    response = client.post(
        "/v1/reasoning/reason",
        json={
            "objective_text": "what is the capital of France?",
            "user_id": str(user_id),
            "requesting_engine": "test",
            "reasoning_mode_hint": "reactive",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_override_confirm_keeps_the_decision(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    body = _reason(client, uuid4())

    response = client.post(
        f"/v1/reasoning/decisions/{body['decision_id']}/override",
        json={"reasoning_process_id": body["reasoning_process_id"], "action": "confirm"},
    )
    assert response.status_code == 200
    assert response.json()["human_override"]["action"] == "confirm"
    process = repository.processes[UUID(body["reasoning_process_id"])]
    assert process.status == "decided"


def test_override_reject_abandons_the_process(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    body = _reason(client, uuid4())

    response = client.post(
        f"/v1/reasoning/decisions/{body['decision_id']}/override",
        json={"reasoning_process_id": body["reasoning_process_id"], "action": "reject"},
    )
    assert response.status_code == 200
    process = repository.processes[UUID(body["reasoning_process_id"])]
    assert process.status == "abandoned"


def test_override_redirect_requires_redirect_alternative_id(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness
    body = _reason(client, uuid4())

    response = client.post(
        f"/v1/reasoning/decisions/{body['decision_id']}/override",
        json={"reasoning_process_id": body["reasoning_process_id"], "action": "redirect"},
    )
    assert response.status_code == 400


def test_override_missing_decision_returns_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    response = client.post(
        f"/v1/reasoning/decisions/{uuid4()}/override",
        json={"reasoning_process_id": str(uuid4()), "action": "confirm"},
    )
    assert response.status_code == 404


def test_reason_stream_emits_stage_events_and_completes(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    with client.stream(
        "POST",
        "/v1/reasoning/reason/stream",
        json={
            "objective_text": "what is the capital of France?",
            "user_id": str(uuid4()),
            "requesting_engine": "test",
            "reasoning_mode_hint": "reactive",
        },
    ) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    data_lines = [line for line in lines if line.startswith("data:")]
    assert data_lines  # at least one stage event was emitted
    # real stage payloads were emitted, not just the final "complete" event
    assert any("__" not in line for line in data_lines[:-1])

"""End-to-end tests through `api/approvals.py` -- the stopgap
`POST /v1/action/approvals/{action_id}/decide` endpoint (TDD 3D §4 point
4), against `create_app()` and a real `TestClient`."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_action_engine.config import Settings
from nova_action_engine.domain.models import PendingApproval
from nova_action_engine.main import create_app

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeActionRepository()
    app = create_app(
        Settings(),
        repository=repository,
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=FakeIdentityPort(),
    )
    with TestClient(app) as client:
        yield client, repository


def test_decide_approves_a_pending_approval(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    action_id = uuid4()
    asyncio.run(
        repository.insert_pending_approval(
            PendingApproval(action_id=action_id, risk="critical", requested_at=datetime.now(UTC))
        )
    )

    response = client.post(
        f"/v1/action/approvals/{action_id}/decide", json={"approved": True}
    )

    assert response.status_code == 200
    assert response.json() == {"action_id": str(action_id), "decision": "approved"}


def test_decide_denies_a_pending_approval(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    action_id = uuid4()
    asyncio.run(
        repository.insert_pending_approval(
            PendingApproval(action_id=action_id, risk="critical", requested_at=datetime.now(UTC))
        )
    )

    response = client.post(
        f"/v1/action/approvals/{action_id}/decide",
        json={"approved": False, "reason": "not authorized"},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "denied"


def test_decide_returns_404_for_an_unknown_action_id(harness) -> None:  # type: ignore[no-untyped-def]
    client, _repository = harness

    response = client.post(
        f"/v1/action/approvals/{uuid4()}/decide", json={"approved": True}
    )

    assert response.status_code == 404


def test_decide_returns_409_for_an_already_decided_approval(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    action_id = uuid4()
    asyncio.run(
        repository.insert_pending_approval(
            PendingApproval(action_id=action_id, risk="critical", requested_at=datetime.now(UTC))
        )
    )
    first = client.post(f"/v1/action/approvals/{action_id}/decide", json={"approved": True})
    assert first.status_code == 200

    second = client.post(f"/v1/action/approvals/{action_id}/decide", json={"approved": False})

    assert second.status_code == 409

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

    response = client.post(f"/v1/action/approvals/{action_id}/decide", json={"approved": True})

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

    response = client.post(f"/v1/action/approvals/{uuid4()}/decide", json={"approved": True})

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


# --- GET /v1/action/approvals (Phase 4B, the Approvals panel) --------------


def _seed(repository, *, decided: bool = False, minutes: int = 0):  # type: ignore[no-untyped-def]
    approval = PendingApproval(
        action_id=uuid4(),
        risk="high",
        requested_at=datetime(2026, 9, 1, 12, minutes, tzinfo=UTC),
        decision="approved" if decided else None,
        decided_at=datetime.now(UTC) if decided else None,
    )
    asyncio.run(repository.insert_pending_approval(approval))
    return approval


def test_listing_approvals_is_empty_when_nothing_is_waiting(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.get("/v1/action/approvals")
    assert response.status_code == 200
    assert response.json() == []


def test_only_undecided_approvals_are_listed(harness) -> None:  # type: ignore[no-untyped-def]
    """The panel answers "what is waiting on me".

    A settled approval in that list is noise that grows without bound, and
    it would also invite a second decision on something already decided --
    which `decide` then rejects with a 409.
    """
    client, repository = harness
    waiting = _seed(repository)
    _seed(repository, decided=True, minutes=1)

    body = client.get("/v1/action/approvals").json()
    assert [row["action_id"] for row in body] == [str(waiting.action_id)]


def test_approvals_are_listed_oldest_first(harness) -> None:  # type: ignore[no-untyped-def]
    """Whatever has been blocked longest is what most likely matters."""
    client, repository = harness
    second = _seed(repository, minutes=5)
    first = _seed(repository, minutes=1)

    body = client.get("/v1/action/approvals").json()
    assert [row["action_id"] for row in body] == [
        str(first.action_id),
        str(second.action_id),
    ]


def test_a_decided_approval_leaves_the_list(harness) -> None:  # type: ignore[no-untyped-def]
    """The list and the decide endpoint must agree about the same record."""
    client, repository = harness
    approval = _seed(repository)
    assert len(client.get("/v1/action/approvals").json()) == 1

    client.post(f"/v1/action/approvals/{approval.action_id}/decide", json={"approved": True})
    assert client.get("/v1/action/approvals").json() == []

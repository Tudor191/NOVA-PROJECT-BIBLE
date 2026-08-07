"""End-to-end tests through `api/identities.py` -- exercises the real
FastAPI app (lifespan-driven) against in-memory fakes for every port (no
real Postgres/Event Bus RPC involved).
"""

from __future__ import annotations

from base64 import b64encode
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from nova_perception_engine.config import Settings
from nova_perception_engine.main import create_app

from tests.fakes.ai_model_port import FakeAIModelOrchestrationPort
from tests.fakes.repository import FakePerceptionRepository


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakePerceptionRepository()
    settings = Settings(template_encryption_key=Fernet.generate_key().decode("ascii"))
    app = create_app(
        settings,
        repository=repository,
        ai_model_port=FakeAIModelOrchestrationPort(),
    )
    with TestClient(app) as client:
        yield client, repository


def _enroll_payload(user_id, *, modality: str = "voice") -> dict:  # type: ignore[no-untyped-def]
    return {
        "user_id": str(user_id),
        "modality": modality,
        "sample_bytes": b64encode(b"raw-audio-sample").decode("ascii"),
    }


def test_enroll_requires_active_consent(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.post("/v1/perception/identities", json=_enroll_payload(uuid4()))
    assert response.status_code == 403


def test_enroll_succeeds_after_consent_granted(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    user_id = uuid4()
    client.post(
        "/v1/perception/consent",
        json={"user_id": str(user_id), "source": "microphone", "scope": "voice enrollment"},
    )

    response = client.post("/v1/perception/identities", json=_enroll_payload(user_id))

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(user_id)
    assert body["modality"] == "voice"
    assert "template_ciphertext" not in body


def test_enrolled_identity_never_exposes_a_template_in_list_response(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    user_id = uuid4()
    client.post(
        "/v1/perception/consent",
        json={"user_id": str(user_id), "source": "microphone", "scope": "voice enrollment"},
    )
    client.post("/v1/perception/identities", json=_enroll_payload(user_id))

    response = client.get("/v1/perception/identities", params={"user_id": str(user_id)})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "template_ciphertext" not in body[0]


def test_revoke_identity_hard_deletes_it(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    user_id = uuid4()
    client.post(
        "/v1/perception/consent",
        json={"user_id": str(user_id), "source": "microphone", "scope": "voice enrollment"},
    )
    identity_id = client.post("/v1/perception/identities", json=_enroll_payload(user_id)).json()[
        "identity_id"
    ]

    response = client.delete(f"/v1/perception/identities/{identity_id}")

    assert response.status_code == 204
    assert identity_id not in {str(k) for k in repository.identities}


def test_revoke_unknown_identity_is_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    response = client.delete(f"/v1/perception/identities/{uuid4()}")
    assert response.status_code == 404

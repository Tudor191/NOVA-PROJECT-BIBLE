"""`domain/enrollment.py` -- encrypted template round-trip and the enroll
flow (docs/design/phase-2d/03-perception-engine.md Sec11, Sec16)."""

from __future__ import annotations

from uuid import uuid4

from cryptography.fernet import Fernet
from nova_perception_engine.domain.enrollment import decrypt_embedding, encrypt_embedding, enroll

from tests.fakes.repository import FakePerceptionRepository

_KEY = Fernet.generate_key()


def test_encrypt_decrypt_round_trip_recovers_the_embedding() -> None:
    embedding = [0.1, 0.2, 0.3, -0.5]
    ciphertext = encrypt_embedding(embedding, key=_KEY)
    assert ciphertext != embedding
    assert decrypt_embedding(ciphertext, key=_KEY) == embedding


def test_ciphertext_is_never_plaintext_json() -> None:
    embedding = [0.1, 0.2]
    ciphertext = encrypt_embedding(embedding, key=_KEY)
    assert b"0.1" not in ciphertext


async def test_enroll_stores_encrypted_template_never_plaintext() -> None:
    repository = FakePerceptionRepository()
    user_id = uuid4()
    embedding = [0.4, 0.5, 0.6]

    identity = await enroll(
        repository,
        user_id=user_id,
        modality="voice",
        embedding=embedding,
        encryption_key=_KEY,
    )

    stored = repository.identities[identity.identity_id]
    assert stored.template_ciphertext != embedding
    assert decrypt_embedding(stored.template_ciphertext, key=_KEY) == embedding


async def test_enroll_records_correct_modality_and_user() -> None:
    repository = FakePerceptionRepository()
    user_id = uuid4()

    identity = await enroll(
        repository, user_id=user_id, modality="face", embedding=[0.1], encryption_key=_KEY
    )

    assert identity.user_id == user_id
    assert identity.modality == "face"
    assert identity.revoked_at is None

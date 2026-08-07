"""Identity Registry enrollment (docs/design/phase-2d/03-perception-engine.md
Sec0.1, Sec6.2, Sec7.1, Sec11) -- the one place the encryption invariant is
enforced and testable without a real database: every embedding is encrypted
here, before it is ever handed to the repository layer, and decrypted here,
after the repository layer returns it for a matching pass. The repository
itself never sees a plaintext embedding and never performs encryption --
`domain/enrollment.py` owns that boundary exclusively (Sec16).

Fernet (symmetric, authenticated encryption) is deliberately simple for this
phase's single-user default (ADR-025) -- the key itself is supplied by the
caller (`config.py`'s `template_encryption_key`, never hardcoded here),
managed outside this engine's own schema per standard secrets-management
practice (Sec11)."""

from __future__ import annotations

import json
from uuid import UUID

from cryptography.fernet import Fernet

from nova_perception_engine.domain.models import EnrolledIdentity, Modality
from nova_perception_engine.domain.ports import PerceptionRepository

__all__ = ["decrypt_embedding", "encrypt_embedding", "enroll"]


def encrypt_embedding(embedding: list[float], *, key: bytes) -> bytes:
    fernet = Fernet(key)
    return fernet.encrypt(json.dumps(embedding).encode("utf-8"))


def decrypt_embedding(ciphertext: bytes, *, key: bytes) -> list[float]:
    fernet = Fernet(key)
    return json.loads(fernet.decrypt(ciphertext).decode("utf-8"))


async def enroll(
    repository: PerceptionRepository,
    *,
    user_id: UUID,
    modality: Modality,
    embedding: list[float],
    encryption_key: bytes,
) -> EnrolledIdentity:
    """Sec3.1's enrollment flow -- the caller (`api/identities.py`) has
    already verified active consent (`domain/consent.py`) before this is
    ever called; this function performs no consent check of its own, the
    same "one gate, one place" discipline every prior engine's write paths
    follow."""
    ciphertext = encrypt_embedding(embedding, key=encryption_key)
    identity = EnrolledIdentity(
        user_id=user_id, modality=modality, template_ciphertext=ciphertext
    )
    return await repository.enroll_identity(identity)

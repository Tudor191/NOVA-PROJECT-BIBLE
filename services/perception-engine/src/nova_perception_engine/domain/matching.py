"""Biometric template matching (docs/design/phase-2d/03-perception-engine.md
Sec6.2, Sec7.1, Sec15) -- small, in-process cosine-similarity computation
over encrypted-then-decrypted-in-memory embeddings, never a vector index
(Sec15's own no-embeddings-store reasoning, mirroring ADR-017). Decryption
happens here, alongside the comparison, for the same "domain/ owns the
encryption boundary" reason `domain/enrollment.py` owns encryption on the
write side (Sec16)."""

from __future__ import annotations

import math
from uuid import UUID

from nova_perception_engine.domain.enrollment import decrypt_embedding
from nova_perception_engine.domain.models import EnrolledIdentity

__all__ = ["best_match", "cosine_similarity"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    # Cosine similarity is in [-1, 1]; clamped to [0, 1] since a negative
    # similarity carries no meaningful "match confidence" for this use.
    return max(0.0, dot / (norm_a * norm_b))


def best_match(
    query_embedding: list[float],
    candidates: list[EnrolledIdentity],
    *,
    encryption_key: bytes,
) -> tuple[UUID, float] | None:
    """Returns `(identity_id, confidence)` for the highest-scoring candidate,
    or `None` if `candidates` is empty. Never applies a threshold itself --
    that judgment belongs to `domain/identity_fusion.py`'s fusion step, not
    the matching step (Sec8's own single-responsibility split: matching
    scores, fusion decides)."""
    if not candidates:
        return None
    scored = [
        (
            c.identity_id,
            cosine_similarity(
                query_embedding, decrypt_embedding(c.template_ciphertext, key=encryption_key)
            ),
        )
        for c in candidates
    ]
    return max(scored, key=lambda item: item[1])

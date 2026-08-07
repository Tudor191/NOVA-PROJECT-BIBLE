"""`domain/matching.py` (docs/design/phase-2d/03-perception-engine.md §6.2,
§7.1) -- cosine similarity and best-match selection over encrypted
templates."""

from __future__ import annotations

from uuid import uuid4

from cryptography.fernet import Fernet
from nova_perception_engine.domain.enrollment import encrypt_embedding
from nova_perception_engine.domain.matching import best_match, cosine_similarity
from nova_perception_engine.domain.models import EnrolledIdentity

_KEY = Fernet.generate_key()


def test_cosine_similarity_identical_vectors_is_one() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_negative_correlation_is_clamped_to_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_cosine_similarity_mismatched_lengths_is_zero() -> None:
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_cosine_similarity_empty_vectors_is_zero() -> None:
    assert cosine_similarity([], []) == 0.0


def _template(embedding: list[float], *, user_id) -> EnrolledIdentity:  # type: ignore[no-untyped-def]
    return EnrolledIdentity(
        user_id=user_id,
        modality="voice",
        template_ciphertext=encrypt_embedding(embedding, key=_KEY),
    )


def test_best_match_returns_none_for_no_candidates() -> None:
    assert best_match([1.0, 0.0], [], encryption_key=_KEY) is None


def test_best_match_picks_the_highest_scoring_candidate() -> None:
    user_id = uuid4()
    close = _template([1.0, 0.0, 0.0], user_id=user_id)
    far = _template([0.0, 1.0, 0.0], user_id=user_id)

    result = best_match([1.0, 0.0, 0.0], [far, close], encryption_key=_KEY)

    assert result is not None
    identity_id, score = result
    assert identity_id == close.identity_id
    assert score == 1.0

from uuid import uuid4

from nova_memory_engine.domain.models import MemoryType
from nova_memory_engine.domain.ranking import RankingCandidate, RankingWeights, rank


def _candidate(**overrides: object) -> RankingCandidate:
    defaults: dict[str, object] = {
        "memory_id": uuid4(),
        "memory_type": MemoryType.EPISODIC,
        "content": "some memory",
        "importance_score": 0.5,
        "similarity": None,
        "recency_decay": None,
        "confidence": None,
    }
    defaults.update(overrides)
    return RankingCandidate(**defaults)  # type: ignore[arg-type]


def test_rank_sorts_descending_by_score() -> None:
    low = _candidate(importance_score=0.1)
    high = _candidate(importance_score=0.9)

    results = rank([low, high])

    assert [r.memory_id for r in results] == [high.memory_id, low.memory_id]


def test_rank_preserves_component_scores_for_explainability() -> None:
    candidate = _candidate(similarity=0.8, recency_decay=0.6, confidence=0.7, importance_score=0.5)

    [result] = rank([candidate])

    assert result.similarity == 0.8
    assert result.recency_decay == 0.6
    assert result.confidence == 0.7
    assert result.importance_score == 0.5
    assert result.content == candidate.content
    assert result.memory_type == candidate.memory_type


def test_missing_component_scores_contribute_zero_not_excluded() -> None:
    timeline_only = _candidate(importance_score=0.5, similarity=None)

    [result] = rank([timeline_only])

    weights = RankingWeights()
    assert result.score == weights.importance * 0.5


def test_higher_similarity_never_decreases_score() -> None:
    low = _candidate(similarity=0.1)
    high = _candidate(similarity=0.9)

    [low_result] = rank([low])
    [high_result] = rank([high])

    assert high_result.score >= low_result.score


def test_rank_with_no_candidates_returns_empty() -> None:
    assert rank([]) == []

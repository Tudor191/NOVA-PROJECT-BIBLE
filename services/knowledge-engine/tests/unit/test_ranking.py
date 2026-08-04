from datetime import UTC, datetime, timedelta

from nova_knowledge_engine.domain.models import KnowledgeLayer
from nova_knowledge_engine.domain.ranking import RankingCandidate, rank, recency_decay


def test_recency_decay_halves_at_half_life() -> None:
    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)
    assert recency_decay(thirty_days_ago, now=now, half_life_days=30.0) == 1 / 2


def test_higher_layer_and_similarity_outrank_lower() -> None:
    now = datetime.now(UTC)
    strong = RankingCandidate(
        node_id="a",
        label="Concept",
        name="A",
        layer=KnowledgeLayer.EXPERT,
        confidence=0.9,
        updated_at=now,
        similarity=0.9,
    )
    weak = RankingCandidate(
        node_id="b",
        label="Concept",
        name="B",
        layer=KnowledgeLayer.RAW,
        confidence=0.5,
        updated_at=now,
        similarity=0.1,
    )
    ranked = rank([weak, strong], now=now)
    assert [r.node_id for r in ranked] == ["a", "b"]


def test_rank_respects_limit() -> None:
    now = datetime.now(UTC)
    candidates = [
        RankingCandidate(
            node_id=str(i), label="Concept", name=str(i), layer=KnowledgeLayer.RAW,
            confidence=0.5, updated_at=now,
        )
        for i in range(5)
    ]
    ranked = rank(candidates, now=now, limit=2)
    assert len(ranked) == 2

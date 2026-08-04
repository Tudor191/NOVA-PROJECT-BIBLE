from datetime import UTC, datetime, timedelta

from nova_world_model_engine.domain import attention
from nova_world_model_engine.domain.models import AttentionEntry


def test_current_score_at_boost_time_equals_raw_weight() -> None:
    now = datetime.now(UTC)
    entry = AttentionEntry(entity_id="a", raw_weight=1.0, last_boosted_at=now)
    assert attention.current_score(entry, now=now) == 1.0


def test_current_score_decays_monotonically_between_boosts() -> None:
    boosted_at = datetime.now(UTC)
    entry = AttentionEntry(entity_id="a", raw_weight=1.0, last_boosted_at=boosted_at)
    scores = [
        attention.current_score(entry, now=boosted_at + timedelta(minutes=m))
        for m in range(0, 60, 5)
    ]
    assert all(earlier >= later for earlier, later in zip(scores, scores[1:], strict=False))


def test_current_score_halves_at_the_half_life() -> None:
    boosted_at = datetime.now(UTC)
    half_life = timedelta(minutes=30)
    entry = AttentionEntry(entity_id="a", raw_weight=1.0, last_boosted_at=boosted_at)
    score = attention.current_score(entry, now=boosted_at + half_life, half_life=half_life)
    # exp(-1) at t=half_life for this literal formula (not the 0.5 convention)
    import math

    assert score == math.exp(-1)


def test_rank_by_attention_orders_descending() -> None:
    now = datetime.now(UTC)
    entries = [
        AttentionEntry(entity_id="low", raw_weight=0.1, last_boosted_at=now),
        AttentionEntry(entity_id="high", raw_weight=5.0, last_boosted_at=now),
    ]
    ranked = attention.rank_by_attention(entries, now=now)
    assert [r.entity_id for r in ranked] == ["high", "low"]


def test_boost_adds_never_overwrites() -> None:
    now = datetime.now(UTC)
    entry = attention.boost(None, entity_id="a", amount=1.0, at=now)
    assert entry.raw_weight == 1.0
    boosted_again = attention.boost(entry, entity_id="a", amount=2.0, at=now)
    assert boosted_again.raw_weight == 3.0

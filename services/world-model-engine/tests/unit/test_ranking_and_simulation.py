"""`domain/ranking.py` and `domain/simulation.py`, which had no test at all.

Each is tested against what its module docstring promises, not against
whatever it happens to return:

* **ranking** -- relevance is Attention alone (docs/design/phase-1/
  03-world-model-engine.md §10: no similarity score to blend in), so an
  object Attention has never scored ranks as `0.0`, not as absent;
* **simulation** -- a Phase 1 stub whose "entire job is honesty": a caller
  must be able to tell "not implemented" from "confidently predicted nothing
  will happen", so the stub answers with zero confidence and says why.
"""

from __future__ import annotations

from uuid import uuid4

from nova_world_model_engine.domain.attention import ScoredEntity
from nova_world_model_engine.domain.models import WorldObject
from nova_world_model_engine.domain.ranking import rank_objects
from nova_world_model_engine.domain.simulation import ProposedAction, simulate

USER = uuid4()


def _object(object_id: str) -> WorldObject:
    return WorldObject(object_id=object_id, label=object_id, user_id=USER)


def test_objects_are_ordered_by_attention_score_highest_first() -> None:
    objects = [_object("a"), _object("b"), _object("c")]
    attention = [ScoredEntity("a", 0.2), ScoredEntity("b", 0.9), ScoredEntity("c", 0.5)]

    ranked = rank_objects(objects, attention)

    assert [r.object.object_id for r in ranked] == ["b", "c", "a"]
    assert [r.attention_score for r in ranked] == [0.9, 0.5, 0.2]


def test_an_object_attention_never_scored_ranks_last_at_zero_and_is_kept() -> None:
    ranked = rank_objects([_object("unscored"), _object("seen")], [ScoredEntity("seen", 0.1)])

    assert [(r.object.object_id, r.attention_score) for r in ranked] == [
        ("seen", 0.1),
        ("unscored", 0.0),
    ]


def test_a_score_for_an_object_not_listed_adds_nothing() -> None:
    ranked = rank_objects([_object("a")], [ScoredEntity("elsewhere", 1.0)])
    assert [r.object.object_id for r in ranked] == ["a"]


def test_the_limit_keeps_only_the_most_relevant() -> None:
    objects = [_object(str(i)) for i in range(15)]
    attention = [ScoredEntity(str(i), i / 100) for i in range(15)]

    ranked = rank_objects(objects, attention)
    assert len(ranked) == 10
    assert ranked[0].object.object_id == "14"

    assert [r.object.object_id for r in rank_objects(objects, attention, limit=2)] == ["14", "13"]


async def test_the_simulation_stub_claims_no_confidence_and_says_it_is_not_implemented() -> None:
    outcome = await simulate(ProposedAction(action_type="file.delete", target_object_id="f:1"))

    assert outcome.confidence == 0.0
    assert "not yet implemented" in outcome.reason
    # No plausible-looking predicted state is invented in place of an answer.
    assert outcome.predicted_state is None

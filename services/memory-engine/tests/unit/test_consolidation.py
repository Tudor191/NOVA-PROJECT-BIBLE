from uuid import uuid4

from nova_memory_engine.domain import consolidation
from nova_memory_engine.domain.models import LifecycleState as S


def _candidate(**overrides: object) -> consolidation.ConsolidationCandidate:
    defaults: dict[str, object] = {
        "memory_id": uuid4(),
        "user_id": uuid4(),
        "project_id": None,
        "embedding": None,
        "confidence": None,
        "importance_score": 0.5,
        "lifecycle_state": S.ACTIVE,
        "days_since_last_access": 0.0,
        "has_active_project_reference": False,
    }
    defaults.update(overrides)
    return consolidation.ConsolidationCandidate(**defaults)  # type: ignore[arg-type]


def test_near_identical_embeddings_within_same_user_are_merged() -> None:
    user_id = uuid4()
    a = _candidate(user_id=user_id, embedding=[1.0, 0.0, 0.0], confidence=0.9)
    b = _candidate(user_id=user_id, embedding=[0.99, 0.01, 0.0], confidence=0.5)

    [merge] = consolidation.find_duplicate_clusters([a, b])

    assert merge.keep_id == a.memory_id  # higher confidence wins
    assert merge.superseded_ids == (b.memory_id,)


def test_dissimilar_embeddings_are_not_merged() -> None:
    user_id = uuid4()
    a = _candidate(user_id=user_id, embedding=[1.0, 0.0, 0.0])
    b = _candidate(user_id=user_id, embedding=[0.0, 1.0, 0.0])

    assert consolidation.find_duplicate_clusters([a, b]) == []


def test_similar_embeddings_across_different_users_are_never_merged() -> None:
    a = _candidate(user_id=uuid4(), embedding=[1.0, 0.0, 0.0])
    b = _candidate(user_id=uuid4(), embedding=[1.0, 0.0, 0.0])

    assert consolidation.find_duplicate_clusters([a, b]) == []


def test_candidates_without_embeddings_never_participate() -> None:
    user_id = uuid4()
    a = _candidate(user_id=user_id, embedding=None)
    b = _candidate(user_id=user_id, embedding=None)

    assert consolidation.find_duplicate_clusters([a, b]) == []


def test_plan_lifecycle_advances_matches_lifecycle_module() -> None:
    stale = _candidate(
        lifecycle_state=S.ACTIVE, days_since_last_access=30.0, importance_score=0.1
    )

    [advance] = consolidation.plan_lifecycle_advances([stale])

    assert advance.memory_id == stale.memory_id
    assert advance.from_state == S.ACTIVE
    assert advance.to_state == S.WEAK


def test_plan_lifecycle_advances_skips_records_with_no_transition() -> None:
    fresh = _candidate(lifecycle_state=S.ACTIVE, days_since_last_access=1.0, importance_score=0.9)

    assert consolidation.plan_lifecycle_advances([fresh]) == []


def test_plan_consolidation_excludes_superseded_records_from_lifecycle_advances() -> None:
    user_id = uuid4()
    keep = _candidate(
        user_id=user_id,
        embedding=[1.0, 0.0],
        confidence=0.9,
        lifecycle_state=S.ACTIVE,
        days_since_last_access=30.0,
        importance_score=0.1,
    )
    superseded = _candidate(
        user_id=user_id,
        embedding=[0.99, 0.01],
        confidence=0.1,
        lifecycle_state=S.ACTIVE,
        days_since_last_access=30.0,
        importance_score=0.1,
    )

    plan = consolidation.plan_consolidation([keep, superseded])

    assert len(plan.merges) == 1
    advanced_ids = {a.memory_id for a in plan.lifecycle_advances}
    assert superseded.memory_id not in advanced_ids
    assert keep.memory_id in advanced_ids

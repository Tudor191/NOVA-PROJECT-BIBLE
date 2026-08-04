"""`workers/consolidation_worker.py` -- duplicate merge, passive lifecycle advance,
and grace-period hard delete, end-to-end against `FakeMemoryRepository` (docs/design/
phase-1/01-memory-engine.md §6, §19's "consolidation worker against seeded
duplicate fixtures" requirement).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nova_memory_engine.domain.models import LifecycleState, MemoryRecord, MemoryType
from nova_memory_engine.workers.consolidation_worker import (
    run_consolidation,
    run_short_term_expiry,
)

from tests.fakes.memory_repository import FakeMemoryRepository


def _seed(repo: FakeMemoryRepository, **overrides: object) -> MemoryRecord:
    defaults: dict[str, object] = {
        "memory_type": MemoryType.SEMANTIC,
        "content": "seeded memory",
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    record = MemoryRecord(**defaults)
    repo.memories[record.id] = record
    return record


async def test_near_duplicates_are_merged_choosing_highest_confidence() -> None:
    repo = FakeMemoryRepository()
    user_id = uuid4()
    keep = _seed(repo, user_id=user_id, embedding=[1.0, 0.0], confidence=0.9)
    superseded = _seed(repo, user_id=user_id, embedding=[0.999, 0.001], confidence=0.2)

    await run_consolidation(repo)

    assert repo.memories[keep.id].lifecycle_state == LifecycleState.ACTIVE
    assert repo.memories[superseded.id].lifecycle_state == LifecycleState.SCHEDULED_FOR_DELETION


async def test_consolidation_run_is_recorded_with_correct_counts() -> None:
    repo = FakeMemoryRepository()
    user_id = uuid4()
    _seed(repo, user_id=user_id, embedding=[1.0, 0.0], confidence=0.9)
    _seed(repo, user_id=user_id, embedding=[0.999, 0.001], confidence=0.2)

    await run_consolidation(repo)

    [run] = repo.consolidation_runs.values()
    assert run.status == "completed"
    assert run.records_scanned == 2
    assert run.records_merged == 1


async def test_stale_active_memory_advances_to_weak() -> None:
    repo = FakeMemoryRepository()
    now = datetime.now(UTC)
    stale = _seed(
        repo,
        lifecycle_state=LifecycleState.ACTIVE,
        importance_score=0.1,
        last_accessed_at=now - timedelta(days=45),
        created_at=now - timedelta(days=45),
    )

    await run_consolidation(repo, now=now)

    assert repo.memories[stale.id].lifecycle_state == LifecycleState.WEAK


async def test_scheduled_deletion_past_grace_period_is_hard_deleted() -> None:
    repo = FakeMemoryRepository()
    now = datetime.now(UTC)
    scheduled = _seed(
        repo,
        lifecycle_state=LifecycleState.SCHEDULED_FOR_DELETION,
        updated_at=now - timedelta(days=31),
    )

    await run_consolidation(repo, now=now)

    assert repo.memories[scheduled.id].lifecycle_state == LifecycleState.DELETED


async def test_scheduled_deletion_within_grace_period_is_untouched() -> None:
    repo = FakeMemoryRepository()
    now = datetime.now(UTC)
    scheduled = _seed(
        repo,
        lifecycle_state=LifecycleState.SCHEDULED_FOR_DELETION,
        updated_at=now - timedelta(days=5),
    )

    await run_consolidation(repo, now=now)

    assert repo.memories[scheduled.id].lifecycle_state == LifecycleState.SCHEDULED_FOR_DELETION


async def test_consolidation_run_marked_failed_on_exception() -> None:
    repo = FakeMemoryRepository()

    async def _boom(**_kwargs: object) -> list[MemoryRecord]:
        raise RuntimeError("simulated repository failure")

    repo.list_candidates_for_consolidation = _boom  # type: ignore[method-assign]

    try:
        await run_consolidation(repo)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError to propagate")

    [run] = repo.consolidation_runs.values()
    assert run.status == "failed"


async def test_short_term_expiry_removes_only_expired_records() -> None:
    from nova_memory_engine.domain.models import ShortTermRecord

    repo = FakeMemoryRepository()
    now = datetime.now(UTC)
    expired = ShortTermRecord(
        content="old",
        category="recent_conversation",
        user_id=uuid4(),
        expires_at=now - timedelta(minutes=1),
    )
    fresh = ShortTermRecord(
        content="new",
        category="recent_conversation",
        user_id=uuid4(),
        expires_at=now + timedelta(hours=1),
    )
    repo.short_term[expired.id] = expired
    repo.short_term[fresh.id] = fresh

    deleted = await run_short_term_expiry(repo, now=now)

    assert deleted == 1
    assert expired.id not in repo.short_term
    assert fresh.id in repo.short_term

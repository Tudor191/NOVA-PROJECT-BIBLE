"""`domain/context.py`'s `upsert_present_identity`/`clear_present_identities`
(docs/design/phase-2d/03-perception-engine.md §0.6) -- the additive
`ActiveContext.present_identities` extension, exercised against
`FakeContextRepository`/`FakeWorldHistoryRepository`."""

from __future__ import annotations

from uuid import uuid4

from nova_world_model_engine.domain import context
from nova_world_model_engine.domain.models import PresentIdentitySignal

from tests.fakes.context_repository import FakeContextRepository
from tests.fakes.history_repository import FakeWorldHistoryRepository


async def test_upsert_present_identity_adds_to_empty_context() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    user_id = uuid4()
    identity_id = uuid4()

    updated = await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(
            identity_id=identity_id, confidence=0.9, modality_summary="voice+face"
        ),
        correlation_id=uuid4(),
    )

    assert len(updated.present_identities) == 1
    assert updated.present_identities[0].identity_id == identity_id
    assert updated.present_identities[0].confidence == 0.9


async def test_upsert_present_identity_replaces_existing_entry_for_same_identity() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    user_id = uuid4()
    identity_id = uuid4()

    await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(
            identity_id=identity_id, confidence=0.6, modality_summary="voice"
        ),
        correlation_id=uuid4(),
    )
    updated = await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(
            identity_id=identity_id, confidence=0.95, modality_summary="voice+face"
        ),
        correlation_id=uuid4(),
    )

    assert len(updated.present_identities) == 1
    assert updated.present_identities[0].confidence == 0.95
    assert updated.present_identities[0].modality_summary == "voice+face"


async def test_upsert_present_identity_keeps_multiple_simultaneous_identities() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    user_id = uuid4()
    first, second = uuid4(), uuid4()

    await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(identity_id=first, confidence=0.9, modality_summary="voice"),
        correlation_id=uuid4(),
    )
    updated = await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(identity_id=second, confidence=0.8, modality_summary="face"),
        correlation_id=uuid4(),
    )

    assert {s.identity_id for s in updated.present_identities} == {first, second}


async def test_upsert_present_identity_preserves_other_active_context_fields() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    user_id = uuid4()
    await context.update_context(
        context_repo,
        history_repo,
        user_id=user_id,
        updates={"task": "coding"},
        confidence=0.7,
        correlation_id=uuid4(),
    )

    updated = await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(
            identity_id=uuid4(), confidence=0.9, modality_summary="voice"
        ),
        correlation_id=uuid4(),
    )

    assert updated.task == "coding"  # untouched by the identity-only update


async def test_clear_present_identities_empties_existing_roster() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()
    user_id = uuid4()
    await context.upsert_present_identity(
        context_repo,
        history_repo,
        user_id=user_id,
        identity=PresentIdentitySignal(
            identity_id=uuid4(), confidence=0.9, modality_summary="voice"
        ),
        correlation_id=uuid4(),
    )

    updated = await context.clear_present_identities(
        context_repo, history_repo, user_id=user_id, correlation_id=uuid4()
    )

    assert updated is not None
    assert updated.present_identities == []


async def test_clear_present_identities_is_a_noop_when_nothing_to_clear() -> None:
    context_repo = FakeContextRepository()
    history_repo = FakeWorldHistoryRepository()

    result = await context.clear_present_identities(
        context_repo, history_repo, user_id=uuid4(), correlation_id=uuid4()
    )

    assert result is None
    assert history_repo.outbox == {}

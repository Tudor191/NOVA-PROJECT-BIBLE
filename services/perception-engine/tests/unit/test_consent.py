"""`domain/consent.py` (docs/design/phase-2d/03-perception-engine.md Sec0.1,
Sec11)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from nova_perception_engine.domain.consent import (
    ConsentRequiredError,
    grant,
    require_active_consent,
    revoke,
)

from tests.fakes.repository import FakePerceptionRepository


async def test_require_active_consent_raises_when_none_granted() -> None:
    repository = FakePerceptionRepository()
    with pytest.raises(ConsentRequiredError):
        await require_active_consent(repository, user_id=uuid4(), source="microphone")


async def test_require_active_consent_passes_after_grant() -> None:
    repository = FakePerceptionRepository()
    user_id = uuid4()
    await grant(repository, user_id=user_id, source="microphone", scope="wake-phrase detection")

    await require_active_consent(repository, user_id=user_id, source="microphone")  # no raise


async def test_revoke_makes_consent_inactive_immediately() -> None:
    repository = FakePerceptionRepository()
    user_id = uuid4()
    await grant(repository, user_id=user_id, source="camera", scope="presence detection")

    revoked = await revoke(repository, user_id=user_id, source="camera")

    assert revoked is not None
    assert revoked.revoked_at is not None
    with pytest.raises(ConsentRequiredError):
        await require_active_consent(repository, user_id=user_id, source="camera")


async def test_revoke_with_no_active_grant_returns_none() -> None:
    repository = FakePerceptionRepository()
    result = await revoke(repository, user_id=uuid4(), source="microphone")
    assert result is None


async def test_consent_is_scoped_per_source() -> None:
    repository = FakePerceptionRepository()
    user_id = uuid4()
    await grant(repository, user_id=user_id, source="microphone", scope="wake-phrase detection")

    with pytest.raises(ConsentRequiredError):
        await require_active_consent(repository, user_id=user_id, source="camera")

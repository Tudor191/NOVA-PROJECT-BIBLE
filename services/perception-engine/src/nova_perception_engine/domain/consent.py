"""Consent management (docs/design/phase-2d/03-perception-engine.md Sec0.1,
Sec4.3, Sec11) -- Doc 22 Principle 8's "explicit per-source consent before
activation, revocable with immediate effect," made concrete. `require_active_
consent` is the one gate every sensor `start()` call and every enrollment
request passes through; `revoke` is modeled as a lifecycle transition
(Sec5), calling the sensor's own `stop()` synchronously within the same
logical operation, so the same tested lifecycle machinery guarantees
immediate effect rather than a separate, easy-to-forget kill switch."""

from __future__ import annotations

from uuid import UUID

from nova_perception_engine.domain.models import ConsentGrant, Source
from nova_perception_engine.domain.ports import PerceptionRepository

__all__ = ["ConsentRequiredError", "grant", "require_active_consent", "revoke"]


class ConsentRequiredError(Exception):
    """Raised when an operation that requires active consent for `source` is
    attempted without it -- never a silent no-op (Sec11)."""

    def __init__(self, source: Source) -> None:
        super().__init__(f"No active consent granted for source {source!r}.")
        self.source = source


async def require_active_consent(
    repository: PerceptionRepository, *, user_id: UUID, source: Source
) -> None:
    if not await repository.has_active_consent(user_id=user_id, source=source):
        raise ConsentRequiredError(source)


async def grant(
    repository: PerceptionRepository, *, user_id: UUID, source: Source, scope: str
) -> ConsentGrant:
    return await repository.grant_consent(
        ConsentGrant(user_id=user_id, source=source, scope=scope)
    )


async def revoke(
    repository: PerceptionRepository, *, user_id: UUID, source: Source
) -> ConsentGrant | None:
    """Sec3.3's revocation flow -- the caller (`api/consent.py`) is
    responsible for calling the corresponding sensor's `stop()` within the
    same request, per Sec5's lifecycle-transition modeling; this function
    only performs the persistence half."""
    return await repository.revoke_consent(user_id=user_id, source=source)

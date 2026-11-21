"""Test doubles for `ConversationalTrustSource`.

`SpyTrustSource` is what makes TDD §4.2's *"order is binding and must be
asserted by test"* an actual assertion rather than a claim: it records whether
it was consulted, so a test can prove a policy denial returned **before** the
trust stage instead of inferring it from a reason string.

`StubTrustSource` supplies a real 2D-D-shaped snapshot so the Trust Engine's
consumption path is exercised end to end even though no transport for the read
exists in this release (`clients/conversational_trust.py`).
"""

from __future__ import annotations

from uuid import UUID

from nova_autonomy_engine.domain.models import TrustInputStatus, TrustMetricSnapshot
from nova_autonomy_engine.domain.ports import ConversationalTrustRead

__all__ = ["SpyTrustSource", "StubTrustSource"]


class SpyTrustSource:
    """Records every consultation. `reads` stays empty when a gate denied
    first, which is the evidence for the ordering requirement."""

    def __init__(self, result: ConversationalTrustRead | None = None) -> None:
        self.reads: list[UUID] = []
        self._result = result or ConversationalTrustRead(status=TrustInputStatus.NO_DATA)

    async def read(self, user_id: UUID) -> ConversationalTrustRead:
        self.reads.append(user_id)
        return self._result

    @property
    def was_consulted(self) -> bool:
        return bool(self.reads)


class StubTrustSource:
    """Returns a fixed, available snapshot built from 2D-D's own field shape."""

    def __init__(
        self,
        *,
        correction_frequency: float | None = 0.0,
        window_session_count: int = 10,
        status: TrustInputStatus = TrustInputStatus.AVAILABLE,
    ) -> None:
        self._status = status
        self._snapshot = (
            None
            if status is TrustInputStatus.UNAVAILABLE
            else TrustMetricSnapshot(
                correction_frequency=correction_frequency,
                window_session_count=window_session_count,
            )
        )

    async def read(self, user_id: UUID) -> ConversationalTrustRead:
        del user_id
        return ConversationalTrustRead(status=self._status, snapshot=self._snapshot)

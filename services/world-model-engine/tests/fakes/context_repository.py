"""`FakeContextRepository` -- an in-memory `domain.ports.ContextRepository`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from nova_world_model_engine.domain.models import ActiveContext, AttentionEntry


class FakeContextRepository:
    def __init__(self) -> None:
        self.contexts: dict[UUID, ActiveContext] = {}
        self.attention: dict[UUID, dict[str, AttentionEntry]] = {}
        self.presence: dict[tuple[UUID, str], tuple[str, datetime]] = {}
        self.unavailable = False
        """Tests set this to simulate Redis being unreachable."""

    async def get_context(self, user_id: UUID) -> ActiveContext | None:
        if self.unavailable:
            raise ConnectionError("simulated Redis outage")
        return self.contexts.get(user_id)

    async def put_context(self, context: ActiveContext) -> None:
        if self.unavailable:
            raise ConnectionError("simulated Redis outage")
        self.contexts[context.user_id] = context

    async def get_attention(self, user_id: UUID) -> list[AttentionEntry]:
        return list(self.attention.get(user_id, {}).values())

    async def boost_attention(
        self, *, user_id: UUID, entity_id: str, boost: float, at: datetime
    ) -> None:
        from nova_world_model_engine.domain import attention as attention_domain

        entries = self.attention.setdefault(user_id, {})
        entries[entity_id] = attention_domain.boost(
            entries.get(entity_id), entity_id=entity_id, amount=boost, at=at
        )

    async def put_presence(
        self, *, user_id: UUID, device: str, platform: str, at: datetime
    ) -> None:
        self.presence[(user_id, device)] = (platform, at)

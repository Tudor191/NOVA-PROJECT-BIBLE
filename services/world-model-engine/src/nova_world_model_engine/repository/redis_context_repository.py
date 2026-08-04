"""`RedisContextRepository` -- implements `domain.ports.ContextRepository`
against Redis (docs/design/phase-1/03-world-model-engine.md §4). Active
Context's and Attention's primary store, not a cache of anything else
(docs/design/phase-1/00-shared-foundations.md) -- the highest-QPS port in
Phase 1 (`world_model.context.request`, budgeted at p95 < 20ms, §15), so
`get_context` is a single `HGETALL`, never a fan-out.

Key patterns (§4):
    world:context:<user_id>            HASH   {objective, project_id, device,
                                                task, activity, platform,
                                                confidence, updated_at}
    world:attention:<user_id>          ZSET   member=entity_id,
                                                score=raw_attention_weight
    world:attention_ts:<user_id>       HASH   member=entity_id,
                                                value=last_boosted_at (ISO 8601)
    world:presence:<user_id>:<device>  STRING platform, TTL=5min
                                                (heartbeat-refreshed)

`world:attention_ts:<user_id>` is §4's "timestamp stored alongside" the ZSET
score, since a ZSET score can only carry one number and the lazy-decay formula
(`domain/attention.py`) needs both `raw_weight` and `last_boosted_at` to
compute current attention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from nova_world_model_engine.domain.models import ActiveContext, AttentionEntry

if TYPE_CHECKING:
    from redis.asyncio import Redis

PRESENCE_TTL_SECONDS = 300

_CONTEXT_FIELDS = (
    "objective",
    "project_id",
    "device",
    "task",
    "activity",
    "platform",
    "confidence",
    "updated_at",
)


def _context_key(user_id: UUID) -> str:
    return f"world:context:{user_id}"


def _attention_key(user_id: UUID) -> str:
    return f"world:attention:{user_id}"


def _attention_ts_key(user_id: UUID) -> str:
    return f"world:attention_ts:{user_id}"


def _presence_key(user_id: UUID, device: str) -> str:
    return f"world:presence:{user_id}:{device}"


def _decode(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class RedisContextRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_context(self, user_id: UUID) -> ActiveContext | None:
        raw: dict[object, object] = await self._redis.hgetall(_context_key(user_id))  # type: ignore[misc]
        if not raw:
            return None
        decoded = {_decode(k): _decode(v) for k, v in raw.items()}
        return ActiveContext(
            user_id=user_id,
            objective=decoded.get("objective") or None,
            project_id=UUID(decoded["project_id"]) if decoded.get("project_id") else None,
            device=decoded.get("device") or None,
            task=decoded.get("task") or None,
            activity=decoded.get("activity") or None,
            platform=decoded.get("platform") or None,
            confidence=float(decoded["confidence"]) if decoded.get("confidence") else 0.5,
            updated_at=datetime.fromisoformat(decoded["updated_at"])
            if decoded.get("updated_at")
            else datetime.now(UTC),
        )

    async def put_context(self, context: ActiveContext) -> None:
        mapping: dict[str, str] = {
            "confidence": str(context.confidence),
            "updated_at": context.updated_at.isoformat(),
        }
        for field in (
            "objective",
            "project_id",
            "device",
            "task",
            "activity",
            "platform",
        ):
            value = getattr(context, field)
            if value is not None:
                mapping[field] = str(value)
        key = _context_key(context.user_id)
        await self._redis.delete(key)
        if mapping:
            await self._redis.hset(key, mapping=mapping)  # type: ignore[misc]

    async def get_attention(self, user_id: UUID) -> list[AttentionEntry]:
        weights: list[tuple[Any, float]] = await self._redis.zrange(
            _attention_key(user_id), 0, -1, withscores=True
        )
        timestamps: dict[object, object] = await self._redis.hgetall(  # type: ignore[misc]
            _attention_ts_key(user_id)
        )
        decoded_timestamps = {_decode(k): _decode(v) for k, v in timestamps.items()}
        entries = []
        for member, score in weights:
            entity_id = _decode(member)
            raw_ts = decoded_timestamps.get(entity_id)
            last_boosted_at = datetime.fromisoformat(raw_ts) if raw_ts else datetime.now(UTC)
            entries.append(
                AttentionEntry(
                    entity_id=entity_id, raw_weight=float(score), last_boosted_at=last_boosted_at
                )
            )
        return entries

    async def boost_attention(
        self, *, user_id: UUID, entity_id: str, boost: float, at: datetime
    ) -> None:
        await self._redis.zincrby(_attention_key(user_id), boost, entity_id)
        await self._redis.hset(  # type: ignore[misc]
            _attention_ts_key(user_id), entity_id, at.isoformat()
        )

    async def put_presence(
        self, *, user_id: UUID, device: str, platform: str, at: datetime
    ) -> None:
        await self._redis.set(
            _presence_key(user_id, device),
            f"{platform}|{at.isoformat()}",
            ex=PRESENCE_TTL_SECONDS,
        )

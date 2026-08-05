"""`PostgresModelRegistryRepository` -- implements
`domain.ports.ModelRegistryRepository` against SQLAlchemy async, per the
schema in docs/design/phase-2a/00-ai-model-orchestration-engine.md §4.

Registry mutations (`register`/`deregister`) enqueue an outbox row in the same
transaction as the write, the same transactional-outbox convention as every
other engine -- even though this engine owns no graph, the "commit the intent
durably, dispatch separately" pattern is still the right one for reliable
event publishing (design doc §17).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nova_ai_model_orchestration_engine.domain.models import (
    CapabilityScores,
    ConnectorHealth,
    ModelDescriptor,
    PrivacyLevel,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent
from nova_ai_model_orchestration_engine.repository.models import (
    ModelHealthSnapshotORM,
    ModelRegistryORM,
    OutboxEventORM,
)


def _outbox_orm(event: OutboxEvent) -> OutboxEventORM:
    return OutboxEventORM(
        subject=event.subject,
        payload=event.payload,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
    )


def _to_domain(row: ModelRegistryORM) -> ModelDescriptor:
    return ModelDescriptor(
        id=row.id,
        name=row.name,
        version=row.version,
        provider=row.provider,
        connector_type=row.connector_type,
        is_local=row.is_local,
        modalities=row.modalities,
        capability_scores=CapabilityScores(scores=row.capability_scores),
        context_window=row.context_window,
        max_output_tokens=row.max_output_tokens,
        avg_latency_ms=row.avg_latency_ms,
        avg_quality_score=row.avg_quality_score,
        hardware_requirements=row.hardware_requirements,
        license=row.license,
        cost_per_input_token=row.cost_per_input_token,
        cost_per_output_token=row.cost_per_output_token,
        max_privacy_tier=PrivacyLevel(row.max_privacy_tier),
        health_status=row.health_status,
        schema_version=row.schema_version,
    )


class PostgresModelRegistryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def register(
        self, model: ModelDescriptor, *, outbox_event: OutboxEvent | None = None
    ) -> ModelDescriptor:
        async with self._session_factory() as session, session.begin():
            orm = ModelRegistryORM(
                id=model.id,
                name=model.name,
                version=model.version,
                provider=model.provider,
                connector_type=model.connector_type,
                is_local=model.is_local,
                modalities=model.modalities,
                capability_scores=model.capability_scores.scores,
                context_window=model.context_window,
                max_output_tokens=model.max_output_tokens,
                avg_latency_ms=model.avg_latency_ms,
                avg_quality_score=model.avg_quality_score,
                hardware_requirements=model.hardware_requirements,
                license=model.license,
                cost_per_input_token=model.cost_per_input_token,
                cost_per_output_token=model.cost_per_output_token,
                max_privacy_tier=model.max_privacy_tier.value,
                health_status=model.health_status,
                schema_version=model.schema_version,
            )
            session.add(orm)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))
            await session.flush()
            return _to_domain(orm)

    async def get(self, model_id: UUID) -> ModelDescriptor | None:
        async with self._session_factory() as session:
            row = await session.get(ModelRegistryORM, model_id)
            return _to_domain(row) if row is not None else None

    async def list_all(
        self,
        *,
        provider: str | None = None,
        modality: str | None = None,
        health_status: str | None = None,
    ) -> list[ModelDescriptor]:
        async with self._session_factory() as session:
            stmt = select(ModelRegistryORM)
            if provider is not None:
                stmt = stmt.where(ModelRegistryORM.provider == provider)
            if health_status is not None:
                stmt = stmt.where(ModelRegistryORM.health_status == health_status)
            rows = (await session.execute(stmt)).scalars().all()
            models = [_to_domain(row) for row in rows]
            if modality is not None:
                models = [m for m in models if modality in m.modalities]
            return models

    async def deregister(
        self, model_id: UUID, *, outbox_event: OutboxEvent | None = None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(ModelRegistryORM, model_id)
            if row is not None:
                await session.delete(row)
            if outbox_event is not None:
                session.add(_outbox_orm(outbox_event))

    async def update_health(
        self, model_id: UUID, *, status: str, snapshot: ConnectorHealth
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(ModelRegistryORM)
                .where(ModelRegistryORM.id == model_id)
                .values(health_status=status)
            )
            session.add(
                ModelHealthSnapshotORM(
                    model_id=model_id,
                    available=snapshot.available,
                    latency_ms=snapshot.latency_ms,
                    error_rate=snapshot.error_rate,
                )
            )

    async def update_benchmark(
        self, model_id: UUID, *, avg_latency_ms: float, avg_quality_score: float
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(ModelRegistryORM)
                .where(ModelRegistryORM.id == model_id)
                .values(avg_latency_ms=avg_latency_ms, avg_quality_score=avg_quality_score)
            )

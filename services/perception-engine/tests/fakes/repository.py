"""`FakePerceptionRepository` -- an in-memory `domain.ports.
PerceptionRepository`, mirroring `PostgresPerceptionRepository`'s own
behavior (docs/design/phase-2d/03-perception-engine.md Sec15) closely enough
that swapping one for the other in a test changes nothing observable.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nova_perception_engine.domain.models import (
    ConsentGrant,
    EnrolledIdentity,
    IdentityObservation,
    Modality,
    Source,
)
from nova_perception_engine.domain.ports import OutboxEvent, OutboxRow


class FakePerceptionRepository:
    def __init__(self) -> None:
        self.identities: dict[UUID, EnrolledIdentity] = {}
        self.consents: list[ConsentGrant] = []
        self.observations: list[IdentityObservation] = []
        self.sensor_health: dict[str, dict[str, object]] = {}
        self.outbox: dict[UUID, OutboxRow] = {}

    async def enroll_identity(self, identity: EnrolledIdentity) -> EnrolledIdentity:
        self.identities[identity.identity_id] = identity
        return identity

    async def list_identities(self, *, user_id: UUID) -> list[EnrolledIdentity]:
        return [
            i for i in self.identities.values() if i.user_id == user_id and i.revoked_at is None
        ]

    async def get_identity_templates(
        self, *, user_id: UUID, modality: Modality
    ) -> list[EnrolledIdentity]:
        return [
            i
            for i in self.identities.values()
            if i.user_id == user_id and i.modality == modality and i.revoked_at is None
        ]

    async def revoke_identity(self, identity_id: UUID) -> bool:
        if identity_id not in self.identities:
            return False
        del self.identities[identity_id]
        return True

    async def grant_consent(self, grant: ConsentGrant) -> ConsentGrant:
        self.consents.append(grant)
        return grant

    async def revoke_consent(self, *, user_id: UUID, source: Source) -> ConsentGrant | None:
        from datetime import UTC, datetime

        active = [
            c
            for c in self.consents
            if c.user_id == user_id and c.source == source and c.revoked_at is None
        ]
        if not active:
            return None
        latest = active[-1]
        latest.revoked_at = datetime.now(UTC)
        return latest

    async def consent_status(self, *, user_id: UUID) -> list[ConsentGrant]:
        return [c for c in self.consents if c.user_id == user_id]

    async def has_active_consent(self, *, user_id: UUID, source: Source) -> bool:
        return any(
            c.user_id == user_id and c.source == source and c.revoked_at is None
            for c in self.consents
        )

    async def record_identity_observation(
        self, observation: IdentityObservation, *, outbox_event: OutboxEvent | None = None
    ) -> IdentityObservation:
        self.observations.append(observation)
        if outbox_event is not None:
            record_id = uuid4()
            from datetime import UTC, datetime

            self.outbox[record_id] = OutboxRow(
                id=record_id,
                subject=outbox_event.subject,
                payload=outbox_event.payload,
                correlation_id=outbox_event.correlation_id,
                causation_id=outbox_event.causation_id,
                created_at=datetime.now(UTC),
            )
        return observation

    async def record_sensor_health(
        self, *, sensor_id: str, sensor_type: str, status: str, capabilities: list[str]
    ) -> None:
        self.sensor_health[sensor_id] = {
            "sensor_type": sensor_type,
            "status": status,
            "capabilities": capabilities,
        }

    async def enqueue_outbox(self, event: OutboxEvent) -> UUID:
        from datetime import UTC, datetime

        record_id = uuid4()
        self.outbox[record_id] = OutboxRow(
            id=record_id,
            subject=event.subject,
            payload=event.payload,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            created_at=datetime.now(UTC),
        )
        return record_id

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        return list(self.outbox.values())[:limit]

    async def mark_dispatched(self, outbox_id: UUID) -> None:
        self.outbox.pop(outbox_id, None)

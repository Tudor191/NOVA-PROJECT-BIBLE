"""The three Phase 4E subscribed handlers (TDD 4E Sec8.1), against the real app.

Each handler is driven with a real `nova-contracts` payload inside a real
`EventEnvelope` -- the same shapes the bus delivers -- so what is asserted here is
the wire contract, not a convenience struct. The repository is the fake; the
handler, the payload validation, the derivation and the app wiring are all real.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from nova_contracts import (
    AttentionState,
    DecisionRecordedPayload,
    EventEnvelope,
    GazeDirection,
    LongTermMemoryCreatedPayload,
    MemoryType,
    PerceptionAttentionObservedPayload,
    PrivacyLevel,
)
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.domain.models import DomainState, TwinDomain
from nova_digital_twin_engine.events.handlers import (
    make_attention_observed_handler,
    make_decision_recorded_handler,
    make_memory_created_handler,
)
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository


@pytest.fixture(autouse=True)
def _in_memory_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")


def _envelope(subject: str, payload: object, *, source_engine: str) -> EventEnvelope:
    return EventEnvelope(
        subject=subject,
        source_engine=source_engine,
        correlation_id=uuid4(),
        payload=payload.model_dump(mode="json"),  # type: ignore[attr-defined]
    )


def _memory_payload(**overrides: object) -> LongTermMemoryCreatedPayload:
    defaults: dict[str, object] = {
        "memory_id": uuid4(),
        "user_id": uuid4(),
        "memory_type": MemoryType.PROJECT,
        "importance_score": 0.5,
        "privacy_level": PrivacyLevel.INTERNAL,
        "created_at": datetime.now(UTC),
    }
    return LongTermMemoryCreatedPayload(**{**defaults, **overrides})  # type: ignore[arg-type]


async def test_a_created_memory_becomes_evidence_across_the_domains_it_supports() -> None:
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    payload = _memory_payload(
        memory_type=MemoryType.PROCEDURAL,
        project_id=uuid4(),
        knowledge_node_id="concept:alembic",
    )

    async with app.router.lifespan_context(app):
        await make_memory_created_handler(app)(
            _envelope("memory.long_term.created", payload, source_engine="memory-engine")
        )

    domains = {domain for (_, domain, _) in repository.domain_evidence}
    assert domains == {
        TwinDomain.PERSONAL_WORKFLOW,
        TwinDomain.PROJECTS,
        TwinDomain.KNOWLEDGE_PROFILE,
        TwinDomain.SKILL_PROFILE,
        TwinDomain.LEARNING_PROGRESS,
    }
    for domain in domains:
        assert repository.domain_models[(payload.user_id, domain)].evidence_count == 1


async def test_a_historical_created_at_survives_the_handler_into_the_project_model() -> None:
    """**The AC-6 chain's middle link.** The payload's own `created_at` -- weeks in
    the past -- is what the project model's gap is computed from, never the moment
    the event was delivered."""
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    project_id = uuid4()
    written_at = datetime.now(UTC) - timedelta(days=45)
    payload = _memory_payload(project_id=project_id, created_at=written_at)

    async with app.router.lifespan_context(app):
        await make_memory_created_handler(app)(
            _envelope("memory.long_term.created", payload, source_engine="memory-engine")
        )

    row = repository.domain_evidence[(payload.user_id, TwinDomain.PROJECTS, payload.memory_id)]
    assert row.source_created_at == written_at
    assert row.observed_at > written_at, (
        "observed_at must record when this engine learned of it, not when it happened"
    )

    project = repository.project_models[(payload.user_id, project_id)]
    assert project.last_activity_at == written_at
    assert project.gap_days is not None
    assert project.gap_days == pytest.approx(45.0, abs=0.01)


async def test_a_payload_without_created_at_is_reported_not_backfilled() -> None:
    """The field is optional for backwards compatibility (ADR-024). An older
    envelope must surface the absence, not acquire the delivery time -- which
    would silently collapse a gap to zero."""
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    payload = _memory_payload(created_at=None, project_id=uuid4())

    async with app.router.lifespan_context(app):
        await make_memory_created_handler(app)(
            _envelope("memory.long_term.created", payload, source_engine="memory-engine")
        )

    model = repository.domain_models[(payload.user_id, TwinDomain.PROJECTS)]
    assert model.state is DomainState.PARTIALLY_POPULATED
    assert model.reason is not None
    assert model.reason.code.value == "source_timestamp_missing"


@pytest.mark.parametrize(
    "level", [PrivacyLevel.CONFIDENTIAL, PrivacyLevel.HIGHLY_SENSITIVE]
)
async def test_a_restricted_memory_records_nothing_at_all(level: PrivacyLevel) -> None:
    """**Sec14.5 control 6, at the ingestion boundary.** Not filtered on render --
    never recorded, so no layer above has anything to leak."""
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    payload = _memory_payload(
        privacy_level=level, project_id=uuid4(), knowledge_node_id="concept:secret"
    )

    async with app.router.lifespan_context(app):
        await make_memory_created_handler(app)(
            _envelope("memory.long_term.created", payload, source_engine="memory-engine")
        )

    assert repository.domain_evidence == {}
    assert repository.domain_models == {}
    assert repository.project_models == {}


async def test_a_redelivered_event_does_not_inflate_the_evidence_count() -> None:
    """The bus is at-least-once. Idempotency is in the key, not in the handler's
    memory, so a restart cannot double-count."""
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    payload = _memory_payload(project_id=uuid4())

    async with app.router.lifespan_context(app):
        handler = make_memory_created_handler(app)
        envelope = _envelope(
            "memory.long_term.created", payload, source_engine="memory-engine"
        )
        await handler(envelope)
        await handler(envelope)

    model = repository.domain_models[(payload.user_id, TwinDomain.PROJECTS)]
    assert model.evidence_count == 1
    assert repository.project_models[(payload.user_id, payload.project_id)].memory_count == 1


async def test_a_recorded_decision_populates_goals_without_carrying_its_text() -> None:
    """`DecisionRecordedPayload` has no `privacy_level`, so this engine cannot
    privacy-check `objective`/`chosen_alternative` and therefore never stores
    them. Counts and confidences only."""
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)
    payload = DecisionRecordedPayload(
        decision_id=uuid4(),
        memory_id=uuid4(),
        user_id=uuid4(),
        objective="Pick a queue backend for the outbox",
        chosen_alternative="arq over celery",
        confidence_at_decision=0.75,
    )

    async with app.router.lifespan_context(app):
        await make_decision_recorded_handler(app)(
            _envelope("memory.decision.recorded", payload, source_engine="memory-engine")
        )

    model = repository.domain_models[(payload.user_id, TwinDomain.GOALS)]
    assert model.state is DomainState.POPULATED
    assert model.facts["decision_count"] == 1
    assert model.facts["mean_confidence_at_decision"] == pytest.approx(0.75)

    row = repository.domain_evidence[(payload.user_id, TwinDomain.GOALS, payload.decision_id)]
    assert "objective" not in row.attributes
    assert "chosen_alternative" not in row.attributes
    assert "arq over celery" not in str(model.facts)


async def test_an_attention_observation_is_attributed_to_the_single_trusted_user() -> None:
    """`PerceptionAttentionObservedPayload` carries no `user_id`. ADR-025 gives one
    trusted user per instance, so `primary_user_id` is the only candidate -- an
    explicit setting rather than a hard-coded assumption."""
    repository = FakeDigitalTwinRepository()
    settings = Settings()
    app = create_app(settings, repository=repository)
    payload = PerceptionAttentionObservedPayload(
        attention_state=AttentionState.ENGAGED,
        gaze_direction=GazeDirection.TOWARD_DEVICE,
        confidence=0.88,
    )

    async with app.router.lifespan_context(app):
        await make_attention_observed_handler(app)(
            _envelope(
                "perception.attention.observed", payload, source_engine="perception-engine"
            )
        )

    model = repository.domain_models[
        (settings.primary_user_id, TwinDomain.PRODUCTIVITY_PATTERNS)
    ]
    assert model.state is DomainState.POPULATED
    assert model.facts["observation_count"] == 1


async def test_two_distinct_attention_observations_are_two_rows() -> None:
    """Anti-vacuity for the deduplication key: it must make a *redelivery*
    idempotent without collapsing genuinely distinct observations into one."""
    repository = FakeDigitalTwinRepository()
    settings = Settings()
    app = create_app(settings, repository=repository)
    payload = PerceptionAttentionObservedPayload(
        attention_state=AttentionState.ENGAGED,
        gaze_direction=GazeDirection.TOWARD_DEVICE,
        confidence=0.9,
    )

    async with app.router.lifespan_context(app):
        handler = make_attention_observed_handler(app)
        first = _envelope(
            "perception.attention.observed", payload, source_engine="perception-engine"
        )
        second = _envelope(
            "perception.attention.observed", payload, source_engine="perception-engine"
        )
        await handler(first)
        await handler(first)  # redelivery of the same event
        await handler(second)  # a genuinely different observation

    model = repository.domain_models[
        (settings.primary_user_id, TwinDomain.PRODUCTIVITY_PATTERNS)
    ]
    assert model.evidence_count == 2


async def test_no_handler_publishes_or_writes_upstream() -> None:
    """Sec14.5 control 4 and Sec8.2: the three 4E handlers consume and derive.
    Nothing enters the outbox, so nothing can be published as a side effect."""
    repository = FakeDigitalTwinRepository()
    app = create_app(Settings(), repository=repository)

    async with app.router.lifespan_context(app):
        await make_memory_created_handler(app)(
            _envelope(
                "memory.long_term.created",
                _memory_payload(project_id=uuid4()),
                source_engine="memory-engine",
            )
        )

    assert repository.outbox == [], "a 4E handler enqueued an outbox event"

from typing import Any
from uuid import uuid4

import pytest
from nova_ai_model_orchestration_engine.domain import router
from nova_ai_model_orchestration_engine.domain.fallback import FallbackExhaustedError
from nova_ai_model_orchestration_engine.domain.models import (
    Budget,
    CapabilityScores,
    ConnectorHealth,
    ContextComponent,
    GenerateRequest,
    GenerateResult,
    ModelDescriptor,
    PrivacyLevel,
    UsageRecord,
)
from nova_ai_model_orchestration_engine.domain.ports import OutboxEvent, OutboxRow


def _model(
    name: str, *, capability: float = 0.5, cost: float | None = None, **overrides: object
) -> ModelDescriptor:
    defaults: dict[str, object] = {
        "name": name,
        "version": "1.0",
        "provider": "ollama",
        "connector_type": "ollama",
        "is_local": cost is None,
        "modalities": ["text_generation", "tool_calling"],
        "capability_scores": CapabilityScores(scores={"general_conversation": capability}),
        "context_window": 8192,
        "max_output_tokens": 2048,
        "cost_per_input_token": cost,
        "cost_per_output_token": cost,
        "max_privacy_tier": PrivacyLevel.HIGHLY_SENSITIVE,
        "health_status": "healthy",
    }
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


def _request(
    *, task_type: str = "general_conversation", tools: list | None = None
) -> GenerateRequest:
    return GenerateRequest(
        context=[ContextComponent(source="test", text="hello", token_estimate=5)],
        requesting_engine="test",
        task_type=task_type,
        privacy_hint=PrivacyLevel.INTERNAL,
        correlation_id=uuid4(),
        tools=tools or [],
    )


class _FakeConnector:
    """A minimal ModelConnector-shaped test double -- structural typing means it
    satisfies the Protocol without inheriting from it."""

    def __init__(self, connector_type: str = "fake", *, should_fail: bool = False) -> None:
        self.connector_type = connector_type
        self.should_fail = should_fail
        self.calls = 0

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("simulated provider failure")
        return GenerateResult(
            text="ok",
            input_tokens=5,
            output_tokens=5,
            finish_reason="stop",
            structural_confidence=1.0,
        )

    def stream(self, request: GenerateRequest) -> Any:
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(available=True)


def test_estimate_complexity_is_deterministic() -> None:
    req = _request(task_type="reasoning")
    assert router.estimate_complexity(req) == router.estimate_complexity(req)


def test_estimate_complexity_higher_for_reasoning_than_conversation() -> None:
    reasoning = router.estimate_complexity(_request(task_type="reasoning"))
    conversation = router.estimate_complexity(_request(task_type="general_conversation"))
    assert reasoning > conversation


def test_plan_routing_is_pure_and_reproducible() -> None:
    models = [_model("a", capability=0.9), _model("b", capability=0.3)]
    req = _request()
    decision1 = router.plan_routing(req, models)
    decision2 = router.plan_routing(req, models)
    assert decision1.selected_model_id == decision2.selected_model_id
    assert decision1.candidates == decision2.candidates


def test_plan_routing_selects_highest_composite_score() -> None:
    strong = _model("strong", capability=0.95)
    weak = _model("weak", capability=0.1)
    decision = router.plan_routing(_request(), [weak, strong])
    assert decision.selected_model_id == strong.id


def test_plan_routing_every_candidate_visible_in_decision() -> None:
    models = [_model("a"), _model("b"), _model("c")]
    decision = router.plan_routing(_request(), models)
    assert {c.model_id for c in decision.candidates} == {m.id for m in models}


def test_plan_routing_stable_tiebreak_on_equal_scores() -> None:
    # Two models with identical capability, cost, latency -- score identically.
    a = _model("a", capability=0.5)
    b = _model("b", capability=0.5)
    decision1 = router.plan_routing(_request(), [a, b])
    decision2 = router.plan_routing(_request(), [b, a])  # different input order
    assert decision1.selected_model_id == decision2.selected_model_id
    expected = min(a.id, b.id, key=str)
    assert decision1.selected_model_id == expected


def test_plan_routing_explanation_mentions_selected_model() -> None:
    model = _model("only-one")
    decision = router.plan_routing(_request(), [model])
    assert str(model.id) in decision.explanation


def test_plan_routing_flags_privacy_constraint() -> None:
    cloud_only = _model("cloud", cost=0.001, health_status="healthy")
    cloud_only = cloud_only.model_copy(update={"max_privacy_tier": PrivacyLevel.INTERNAL})
    req = GenerateRequest(
        context=[],
        requesting_engine="test",
        privacy_hint=PrivacyLevel.HIGHLY_SENSITIVE,
        correlation_id=uuid4(),
    )
    with pytest.raises(FallbackExhaustedError):
        router.plan_routing(req, [cloud_only])


def test_plan_routing_raises_when_no_eligible_candidates() -> None:
    with pytest.raises(FallbackExhaustedError):
        router.plan_routing(_request(), [])


async def test_route_and_execute_succeeds_on_first_try() -> None:
    model = _model("only-one")
    connector = _FakeConnector()
    outcome = await router.route_and_execute(
        _request(), [model], get_connector=lambda m: connector
    )
    assert outcome.result.text == "ok"
    assert outcome.retry_count == 0
    assert not outcome.fallback_used


async def test_route_and_execute_falls_back_on_failure() -> None:
    failing = _model("failing", capability=0.9)
    working = _model("working", capability=0.1)
    connectors = {failing.id: _FakeConnector(should_fail=True), working.id: _FakeConnector()}
    outcome = await router.route_and_execute(
        _request(), [failing, working], get_connector=lambda m: connectors[m.id]
    )
    assert outcome.fallback_used
    assert outcome.decision.selected_model_id == working.id
    assert outcome.decision.fallback_from == failing.id


async def test_route_and_execute_raises_when_all_candidates_fail() -> None:
    a = _model("a")
    b = _model("b")
    connectors = {a.id: _FakeConnector(should_fail=True), b.id: _FakeConnector(should_fail=True)}
    with pytest.raises(FallbackExhaustedError):
        await router.route_and_execute(
            _request(), [a, b], get_connector=lambda m: connectors[m.id], max_attempts=2
        )


class _FakeUsageRepository:
    """Only `record_usage` is exercised by `execute_and_record`/`embed_and_record` --
    the rest of `UsageRepository` is implemented to satisfy the Protocol's static
    shape but never called by these tests."""

    def __init__(self) -> None:
        self.recorded: list[UsageRecord] = []
        self.outbox_events: list[OutboxEvent] = []

    async def record_usage(
        self, record: UsageRecord, *, outbox_event: OutboxEvent | None = None
    ) -> UsageRecord:
        self.recorded.append(record)
        if outbox_event is not None:
            self.outbox_events.append(outbox_event)
        return record

    async def list_usage(
        self,
        *,
        model_id: Any = None,
        requesting_engine: str | None = None,
        correlation_id: Any = None,
        since: Any = None,
        until: Any = None,
        limit: int = 100,
    ) -> list[UsageRecord]:
        raise NotImplementedError

    async def spend_this_period(self, *, scope: str, scope_ref: str | None) -> float:
        raise NotImplementedError

    async def get_budget(self, *, scope: str, scope_ref: str | None) -> Budget | None:
        raise NotImplementedError

    async def list_budgets(self) -> list[Budget]:
        raise NotImplementedError

    async def upsert_budget(self, budget: Budget) -> Budget:
        raise NotImplementedError

    async def enqueue_outbox(self, event: OutboxEvent) -> Any:
        raise NotImplementedError

    async def list_dispatch_ready(self, *, limit: int = 100) -> list[OutboxRow]:
        raise NotImplementedError

    async def mark_dispatched(self, outbox_id: Any) -> None:
        raise NotImplementedError


def _embedding_model(
    name: str, *, cost: float | None = None, **overrides: object
) -> ModelDescriptor:
    defaults: dict[str, object] = {
        "name": name,
        "version": "1.0",
        "provider": "ollama",
        "connector_type": "ollama",
        "is_local": cost is None,
        "modalities": ["embedding"],
        "capability_scores": CapabilityScores(scores={}),
        "context_window": 8192,
        "max_output_tokens": 2048,
        "cost_per_input_token": cost,
        "cost_per_output_token": cost,
        "max_privacy_tier": PrivacyLevel.HIGHLY_SENSITIVE,
        "health_status": "healthy",
    }
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


class _FakeEmbeddingConnector:
    connector_type = "fake"

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        raise NotImplementedError

    def stream(self, request: GenerateRequest) -> Any:
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.should_fail:
            raise RuntimeError("simulated embedding failure")
        return [[0.1, 0.2] for _ in texts]

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(available=True)


async def test_execute_and_record_persists_success_telemetry() -> None:
    model = _model("only-one")
    connector = _FakeConnector()
    usage_repo = _FakeUsageRepository()
    outcome = await router.execute_and_record(
        _request(), [model], get_connector=lambda m: connector, usage_repository=usage_repo
    )
    assert outcome.result.text == "ok"
    assert len(usage_repo.recorded) == 1
    record = usage_repo.recorded[0]
    assert record.outcome == "success"
    assert record.model_id == model.id
    assert len(usage_repo.outbox_events) == 1
    assert usage_repo.outbox_events[0].subject == "ai_model.request.completed"


async def test_execute_and_record_persists_failure_telemetry_and_reraises() -> None:
    a = _model("a")
    b = _model("b")
    connectors = {a.id: _FakeConnector(should_fail=True), b.id: _FakeConnector(should_fail=True)}
    usage_repo = _FakeUsageRepository()
    with pytest.raises(FallbackExhaustedError):
        await router.execute_and_record(
            _request(),
            [a, b],
            get_connector=lambda m: connectors[m.id],
            usage_repository=usage_repo,
            max_attempts=2,
        )
    assert len(usage_repo.recorded) == 1
    assert usage_repo.recorded[0].outcome == "failed"
    assert usage_repo.outbox_events[0].subject == "ai_model.request.failed"


def test_plan_embedding_routing_selects_cheapest_candidate() -> None:
    expensive = _embedding_model("expensive", cost=0.01)
    cheap = _embedding_model("cheap", cost=0.0001)
    selected = router.plan_embedding_routing([expensive, cheap], privacy_hint=PrivacyLevel.INTERNAL)
    assert selected.id == cheap.id


async def test_route_and_embed_falls_back_on_failure() -> None:
    failing = _embedding_model("failing", cost=0.0)
    working = _embedding_model("working", cost=0.0)
    connectors = {
        failing.id: _FakeEmbeddingConnector(should_fail=True),
        working.id: _FakeEmbeddingConnector(),
    }
    model, embeddings = await router.route_and_embed(
        ["hello"],
        [failing, working],
        privacy_hint=PrivacyLevel.INTERNAL,
        get_connector=lambda m: connectors[m.id],
    )
    assert model.id in (failing.id, working.id)
    assert len(embeddings) == 1


async def test_embed_and_record_persists_success_telemetry() -> None:
    model = _embedding_model("only-one")
    connector = _FakeEmbeddingConnector()
    usage_repo = _FakeUsageRepository()
    selected, embeddings = await router.embed_and_record(
        ["hello", "world"],
        [model],
        privacy_hint=PrivacyLevel.INTERNAL,
        requesting_engine="test",
        correlation_id=uuid4(),
        get_connector=lambda m: connector,
        usage_repository=usage_repo,
    )
    assert selected.id == model.id
    assert len(embeddings) == 2
    assert len(usage_repo.recorded) == 1
    assert usage_repo.recorded[0].outcome == "success"
    assert usage_repo.outbox_events[0].subject == "ai_model.request.completed"

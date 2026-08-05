from uuid import uuid4

import pytest
from nova_contracts import (
    BudgetExceededPayload,
    BudgetScope,
    ContextComponentPayload,
    EmbedReplyPayload,
    EmbedRequestPayload,
    GenerateReplyPayload,
    GenerateRequestPayload,
    ModelHealthChangedPayload,
    ModelHealthStatus,
    ModelRegistryChangedPayload,
    PrivacyLevel,
    RequestCompletedPayload,
    RequestFailedPayload,
    RequestOutcome,
    known_subjects,
    validate_payload,
)
from nova_contracts.registry import payload_model_for
from pydantic import ValidationError


def test_all_ai_model_orchestration_subjects_are_registered() -> None:
    subjects = known_subjects()
    for subject in (
        "ai_model.generate.request",
        "ai_model.generate.reply",
        "ai_model.embed.request",
        "ai_model.embed.reply",
        "ai_model.request.completed",
        "ai_model.request.failed",
        "ai_model.model.registered",
        "ai_model.model.deregistered",
        "ai_model.model.health_changed",
        "ai_model.budget.exceeded",
    ):
        assert subject in subjects


def test_model_registered_deregistered_share_one_payload_model() -> None:
    assert payload_model_for("ai_model.model.registered") is ModelRegistryChangedPayload
    assert payload_model_for("ai_model.model.deregistered") is ModelRegistryChangedPayload


def test_generate_request_defaults_and_schema_version() -> None:
    request = GenerateRequestPayload(
        context=[ContextComponentPayload(source="user_request", text="hi", token_estimate=1)],
        requesting_engine="reasoning-engine",
        correlation_id=uuid4(),
    )
    assert request.privacy_hint is PrivacyLevel.INTERNAL
    assert request.tools == []
    assert request.schema_version == 1


def test_generate_reply_validates_against_registry() -> None:
    validated = validate_payload(
        "ai_model.generate.reply",
        {
            "text": "hello",
            "input_tokens": 10,
            "output_tokens": 5,
            "finish_reason": "stop",
            "structural_confidence": 0.9,
            "model_id": str(uuid4()),
            "provider": "anthropic",
        },
    )
    assert isinstance(validated, GenerateReplyPayload)
    assert validated.tool_calls == []


def test_embed_request_reply_round_trip() -> None:
    request = EmbedRequestPayload(
        texts=["a", "b"], requesting_engine="memory-engine", correlation_id=uuid4()
    )
    assert request.texts == ["a", "b"]

    reply = EmbedReplyPayload(embeddings=[[0.1, 0.2]], model_id=uuid4(), provider="ollama")
    assert len(reply.embeddings) == 1


def test_request_completed_outcome_is_a_closed_set() -> None:
    with pytest.raises(ValidationError):
        RequestCompletedPayload(
            correlation_id=uuid4(),
            requesting_engine="reasoning-engine",
            provider="anthropic",
            model_id=uuid4(),
            input_tokens=1,
            output_tokens=1,
            estimated_cost=0.0,
            latency_ms=10.0,
            outcome="not-a-real-outcome",  # type: ignore[arg-type]
        )

    completed = RequestCompletedPayload(
        correlation_id=uuid4(),
        requesting_engine="reasoning-engine",
        provider="anthropic",
        model_id=uuid4(),
        input_tokens=1,
        output_tokens=1,
        estimated_cost=0.0,
        latency_ms=10.0,
        outcome=RequestOutcome.SUCCESS,
    )
    assert completed.outcome is RequestOutcome.SUCCESS


def test_request_failed_carries_attempted_models() -> None:
    failed = RequestFailedPayload(
        correlation_id=uuid4(),
        requesting_engine="reasoning-engine",
        attempted_model_ids=[uuid4(), uuid4()],
        final_error="all connectors unavailable",
    )
    assert len(failed.attempted_model_ids) == 2


def test_model_health_changed_statuses() -> None:
    changed = ModelHealthChangedPayload(
        model_id=uuid4(),
        previous_status=ModelHealthStatus.HEALTHY,
        new_status=ModelHealthStatus.DEGRADED,
    )
    assert changed.previous_status is ModelHealthStatus.HEALTHY
    assert changed.new_status is ModelHealthStatus.DEGRADED


def test_budget_exceeded_scope_ref_is_optional_for_global() -> None:
    exceeded = BudgetExceededPayload(
        scope=BudgetScope.GLOBAL, limit_amount=100.0, current_spend=101.0
    )
    assert exceeded.scope_ref is None

from nova_ai_model_orchestration_engine.domain import capability_matrix
from nova_ai_model_orchestration_engine.domain.models import (
    CapabilityScores,
    ModelDescriptor,
    PrivacyLevel,
)


def _model(**overrides: object) -> ModelDescriptor:
    defaults: dict[str, object] = {
        "name": "test-model",
        "version": "1.0",
        "provider": "ollama",
        "connector_type": "ollama",
        "is_local": True,
        "modalities": ["text_generation"],
        "capability_scores": CapabilityScores(scores={"general_conversation": 0.7}),
        "context_window": 8192,
        "max_output_tokens": 2048,
        "max_privacy_tier": PrivacyLevel.HIGHLY_SENSITIVE,
        "health_status": "healthy",
    }
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


def test_task_type_maps_to_known_dimension() -> None:
    assert capability_matrix.task_type_to_dimension("programming") == "programming"


def test_unknown_task_type_falls_back_to_general_conversation() -> None:
    assert capability_matrix.task_type_to_dimension("bogus") == "general_conversation"


def test_eligible_candidates_excludes_unhealthy() -> None:
    healthy = _model(health_status="healthy")
    unhealthy = _model(health_status="unhealthy")
    result = capability_matrix.eligible_candidates(
        [healthy, unhealthy], modality="text_generation", privacy_hint=PrivacyLevel.INTERNAL
    )
    assert result == [healthy]


def test_eligible_candidates_excludes_missing_modality() -> None:
    text_only = _model(modalities=["text_generation"])
    result = capability_matrix.eligible_candidates(
        [text_only], modality="embedding", privacy_hint=PrivacyLevel.INTERNAL
    )
    assert result == []


def test_highly_sensitive_request_only_eligible_for_highly_sensitive_ceiling() -> None:
    cloud_model = _model(max_privacy_tier=PrivacyLevel.CONFIDENTIAL, is_local=False)
    local_model = _model(max_privacy_tier=PrivacyLevel.HIGHLY_SENSITIVE, is_local=True)
    result = capability_matrix.eligible_candidates(
        [cloud_model, local_model],
        modality="text_generation",
        privacy_hint=PrivacyLevel.HIGHLY_SENSITIVE,
    )
    assert result == [local_model]


def test_public_request_eligible_for_any_ceiling() -> None:
    model = _model(max_privacy_tier=PrivacyLevel.INTERNAL)
    result = capability_matrix.eligible_candidates(
        [model], modality="text_generation", privacy_hint=PrivacyLevel.PUBLIC
    )
    assert result == [model]

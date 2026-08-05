from uuid import uuid4

from nova_ai_model_orchestration_engine.domain import privacy_classifier
from nova_ai_model_orchestration_engine.domain.models import GenerateRequest, PrivacyLevel


def _request(privacy_hint: PrivacyLevel) -> GenerateRequest:
    return GenerateRequest(
        context=[],
        requesting_engine="test",
        privacy_hint=privacy_hint,
        correlation_id=uuid4(),
    )


def test_classify_returns_the_caller_supplied_hint() -> None:
    result = privacy_classifier.classify(_request(PrivacyLevel.CONFIDENTIAL))
    assert result == PrivacyLevel.CONFIDENTIAL


def test_classify_preserves_highly_sensitive() -> None:
    assert (
        privacy_classifier.classify(_request(PrivacyLevel.HIGHLY_SENSITIVE))
        == PrivacyLevel.HIGHLY_SENSITIVE
    )

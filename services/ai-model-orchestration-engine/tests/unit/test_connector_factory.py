import pytest
from nova_ai_model_orchestration_engine.connectors.anthropic_connector import AnthropicConnector
from nova_ai_model_orchestration_engine.connectors.factory import (
    ConnectorFactory,
    ConnectorUnavailableError,
)
from nova_ai_model_orchestration_engine.connectors.ollama_connector import OllamaConnector
from nova_ai_model_orchestration_engine.domain.models import CapabilityScores, ModelDescriptor


def _model(connector_type: str, **overrides: object) -> ModelDescriptor:
    defaults: dict[str, object] = {
        "name": "m",
        "version": "1.0",
        "provider": connector_type,
        "connector_type": connector_type,
        "is_local": True,
        "modalities": ["text_generation"],
        "capability_scores": CapabilityScores(scores={}),
        "context_window": 8192,
        "max_output_tokens": 2048,
    }
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


def test_builds_ollama_connector() -> None:
    factory = ConnectorFactory(ollama_base_url="http://localhost:11434", anthropic_api_key=None)
    connector = factory.get_connector(_model("ollama"))
    assert isinstance(connector, OllamaConnector)


def test_builds_anthropic_connector_when_key_configured() -> None:
    factory = ConnectorFactory(ollama_base_url="unused", anthropic_api_key="sk-test")
    connector = factory.get_connector(_model("anthropic"))
    assert isinstance(connector, AnthropicConnector)


def test_anthropic_unavailable_without_api_key() -> None:
    factory = ConnectorFactory(ollama_base_url="unused", anthropic_api_key=None)
    with pytest.raises(ConnectorUnavailableError):
        factory.get_connector(_model("anthropic"))


def test_unknown_connector_type_raises() -> None:
    factory = ConnectorFactory(ollama_base_url="unused", anthropic_api_key=None)
    with pytest.raises(ConnectorUnavailableError):
        factory.get_connector(_model("some-future-provider"))


def test_connector_is_cached_per_model_id() -> None:
    factory = ConnectorFactory(ollama_base_url="http://localhost:11434", anthropic_api_key=None)
    model = _model("ollama")
    first = factory.get_connector(model)
    second = factory.get_connector(model)
    assert first is second

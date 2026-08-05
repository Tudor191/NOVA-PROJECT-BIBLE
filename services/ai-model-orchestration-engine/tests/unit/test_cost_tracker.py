from nova_ai_model_orchestration_engine.domain import cost_tracker
from nova_ai_model_orchestration_engine.domain.models import (
    Budget,
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
        "capability_scores": CapabilityScores(),
        "context_window": 8192,
        "max_output_tokens": 2048,
        "max_privacy_tier": PrivacyLevel.HIGHLY_SENSITIVE,
    }
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


def test_local_model_costs_zero() -> None:
    model = _model(cost_per_input_token=None, cost_per_output_token=None)
    assert cost_tracker.estimate_cost(model, input_tokens=1000, output_tokens=500) == 0.0


def test_cloud_model_cost_is_sum_of_input_and_output() -> None:
    model = _model(cost_per_input_token=0.00001, cost_per_output_token=0.00003)
    cost = cost_tracker.estimate_cost(model, input_tokens=1000, output_tokens=500)
    assert cost == 1000 * 0.00001 + 500 * 0.00003


def test_budget_status_under_threshold() -> None:
    budget = Budget(scope="global", limit_amount=100.0, alert_threshold_pct=80)
    over_alert, over_limit = cost_tracker.budget_status(budget, current_spend=50.0)
    assert not over_alert
    assert not over_limit


def test_budget_status_over_alert_threshold_not_limit() -> None:
    budget = Budget(scope="global", limit_amount=100.0, alert_threshold_pct=80)
    over_alert, over_limit = cost_tracker.budget_status(budget, current_spend=85.0)
    assert over_alert
    assert not over_limit


def test_budget_status_over_limit() -> None:
    budget = Budget(scope="global", limit_amount=100.0, alert_threshold_pct=80)
    over_alert, over_limit = cost_tracker.budget_status(budget, current_spend=150.0)
    assert over_alert
    assert over_limit

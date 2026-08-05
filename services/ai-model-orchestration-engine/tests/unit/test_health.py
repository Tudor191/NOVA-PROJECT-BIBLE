from nova_ai_model_orchestration_engine.domain.health import compute_health_status
from nova_ai_model_orchestration_engine.domain.models import ConnectorHealth


def test_unavailable_is_unhealthy() -> None:
    assert compute_health_status(ConnectorHealth(available=False)) == "unhealthy"


def test_available_with_no_error_rate_is_healthy() -> None:
    assert compute_health_status(ConnectorHealth(available=True)) == "healthy"


def test_available_with_low_error_rate_is_healthy() -> None:
    snapshot = ConnectorHealth(available=True, error_rate=0.05)
    assert compute_health_status(snapshot) == "healthy"


def test_available_with_high_error_rate_is_degraded() -> None:
    snapshot = ConnectorHealth(available=True, error_rate=0.5)
    assert compute_health_status(snapshot) == "degraded"


def test_unavailable_wins_over_error_rate() -> None:
    snapshot = ConnectorHealth(available=False, error_rate=0.0)
    assert compute_health_status(snapshot) == "unhealthy"

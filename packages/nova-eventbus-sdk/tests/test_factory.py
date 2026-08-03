import pytest
from nova_eventbus_sdk.backends.in_memory import InMemoryEventBus
from nova_eventbus_sdk.backends.nats import NatsEventBus
from nova_eventbus_sdk.factory import get_event_bus


def test_default_backend_is_nats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVENT_BUS_BACKEND", raising=False)
    bus = get_event_bus()
    assert isinstance(bus, NatsEventBus)


def test_explicit_in_memory_backend() -> None:
    bus = get_event_bus("in_memory")
    assert isinstance(bus, InMemoryEventBus)


def test_env_var_selects_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    bus = get_event_bus()
    assert isinstance(bus, InMemoryEventBus)


def test_unknown_backend_raises_with_available_list() -> None:
    with pytest.raises(ValueError, match="in_memory"):
        get_event_bus("kafka")

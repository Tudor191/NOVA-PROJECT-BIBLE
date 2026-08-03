import json
import logging
from collections.abc import Iterator

import nova_observability.logging as logging_module
import pytest
from nova_observability.logging import _JsonFormatter, configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_logging_state() -> Iterator[None]:
    """`configure_logging` is process-global by design (one root logger); reset that
    global state between tests so tests don't depend on execution order."""
    logging_module._configured = False
    root = logging.getLogger()
    root.handlers = []
    yield
    logging_module._configured = False
    root.handlers = []


def test_json_formatter_produces_valid_json_with_expected_fields() -> None:
    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test-service.component",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "abc-123"  # simulates `extra={"correlation_id": ...}`

    parsed = json.loads(formatter.format(record))

    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test-service.component"
    assert parsed["correlation_id"] == "abc-123"
    assert "timestamp" in parsed


def test_configure_logging_installs_exactly_one_handler() -> None:
    configure_logging("test-service", level="DEBUG")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, _JsonFormatter)


def test_configure_logging_is_idempotent() -> None:
    configure_logging("test-service")
    configure_logging("test-service")
    root = logging.getLogger()
    assert len(root.handlers) == 1


def test_get_logger_returns_standard_logger() -> None:
    logger = get_logger("nova.memory-engine")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "nova.memory-engine"

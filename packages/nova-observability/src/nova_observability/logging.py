"""Structured JSON logging, configured identically across every engine.

Every log line is a single JSON object so the self-hosted Loki + Grafana stack
(docs/architecture/01-technology-stack.md §7) can index and query it without a
bespoke parser per engine.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED_LOG_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                payload[key] = value
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(service_name: str, *, level: str = "INFO") -> None:
    """Configure the root logger for JSON output. Safe to call more than once."""
    global _configured
    root = logging.getLogger()
    root.setLevel(level)
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.handlers = [handler]
    _configured = True
    get_logger(service_name).info("logging configured", extra={"service": service_name})


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

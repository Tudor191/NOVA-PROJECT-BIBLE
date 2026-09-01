"""The external response envelope, per doc 11 §4.

Every response the outside world sees has the same shape:

    {"data": {...}, "meta": {"confidence": ..., "correlation_id": ...,
     "generated_at": ...}, "error": null}

Engines return bare models -- none of the fourteen emits this envelope
itself -- so the gateway is the layer that applies it. That is deliberate:
doc 11 §1 makes `api-gateway` the one external surface, and §4 exists so the
web client's `entities/` layer can handle any endpoint generically.

`confidence` is passed through, never synthesised. Doc 11 §4 surfaces it at
the envelope level as a direct expression of Part 8's Confidence System, so
inventing a value here would corrupt the exact signal the field exists to
carry. When an engine reports no confidence, the field is absent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

CORRELATION_ID_HEADER = "x-correlation-id"


class ResponseMeta(BaseModel):
    correlation_id: str
    generated_at: datetime
    confidence: float | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    upstream_status: int | None = None


class Envelope(BaseModel):
    data: Any | None = None
    meta: ResponseMeta
    error: ErrorDetail | None = None


def new_correlation_id() -> str:
    return str(uuid4())


def _extract_confidence(payload: object) -> float | None:
    """Lift a `confidence` an engine reported at its own top level.

    Only a top-level, numeric, in-range value is lifted. Anything else is
    left where it is rather than guessed at.
    """
    if not isinstance(payload, dict):
        return None
    value = payload.get("confidence")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0.0 <= float(value) <= 1.0:
        return None
    return float(value)


def success(data: Any, correlation_id: str) -> Envelope:
    return Envelope(
        data=data,
        meta=ResponseMeta(
            correlation_id=correlation_id,
            generated_at=datetime.now(UTC),
            confidence=_extract_confidence(data),
        ),
    )


def failure(
    code: str,
    message: str,
    correlation_id: str,
    upstream_status: int | None = None,
) -> Envelope:
    """A failure envelope always carries `error` and never a partial `data`.

    This is the mechanism behind the project's standing rule that a
    degraded upstream must never look like an empty success.
    """
    return Envelope(
        data=None,
        meta=ResponseMeta(
            correlation_id=correlation_id, generated_at=datetime.now(UTC)
        ),
        error=ErrorDetail(code=code, message=message, upstream_status=upstream_status),
    )


class SessionIssueRequest(BaseModel):
    token: str = Field(min_length=1)


class SessionState(BaseModel):
    authenticated: bool

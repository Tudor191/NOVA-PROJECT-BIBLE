"""EventEnvelope: the single wire format every event on the NOVA Event Bus uses.

See docs/architecture/09-event-bus-architecture.md for the full contract this
implements, and ADR-004 (docs/architecture/00-overview-and-decisions.md) for why
this envelope -- not a direct call -- is the only legal way engines exchange state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    """Common envelope wrapping every event published on the Event Bus."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    subject: str = Field(description="Dot-namespaced subject, e.g. 'memory.episodic.created'.")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_engine: str = Field(description="The service/engine that published this event.")
    correlation_id: UUID = Field(
        description="Ties an entire request lifecycle together end-to-end."
    )
    causation_id: UUID | None = Field(
        default=None, description="The event_id of the event that directly caused this one."
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)

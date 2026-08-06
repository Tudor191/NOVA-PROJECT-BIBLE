"""`MemoryClient` -- `domain.ports.MemoryPort` implementation, calling
`memory.retrieve.request` (docs/design/phase-2c/00-executive-cognition-engine.md
§5.3). Used narrowly for historical-outcome lookups (§7.3), never general
recall. Degrades gracefully on timeout -- an empty result, not an exception,
the same read-path degradation discipline every engine's own memory client
already follows.
"""

from __future__ import annotations

from uuid import UUID

from nova_contracts import MemoryRetrieveReplyPayload, MemoryRetrieveRequestPayload

from nova_executive_cognition_engine.domain.models import MemoryReference
from nova_executive_cognition_engine.domain.ports import EventPublisher

__all__ = ["MemoryClient"]

SOURCE_ENGINE = "executive-cognition-engine"
DEFAULT_TIMEOUT_MS = 2000
_SUMMARY_MAX_CHARS = 280


def _summarize(content: str) -> str:
    """§5.3 -- never duplicate a memory's full content into this engine's
    own records, even in a lightweight in-memory reference."""
    if len(content) <= _SUMMARY_MAX_CHARS:
        return content
    return content[: _SUMMARY_MAX_CHARS - 1].rstrip() + "…"


class MemoryClient:
    def __init__(
        self, event_publisher: EventPublisher, *, timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> None:
        self._event_publisher = event_publisher
        self._timeout_ms = timeout_ms

    async def retrieve(
        self,
        *,
        user_id: UUID,
        query: str,
        limit: int = 10,
        correlation_id: UUID | None = None,
    ) -> list[MemoryReference]:
        try:
            reply = await self._event_publisher.request(
                "memory.retrieve.request",
                MemoryRetrieveRequestPayload(user_id=user_id, query_text=query, limit=limit),
                source_engine=SOURCE_ENGINE,
                correlation_id=correlation_id,
                timeout_ms=self._timeout_ms,
            )
        except TimeoutError:
            return []
        parsed = MemoryRetrieveReplyPayload.model_validate(reply.payload)
        return [
            MemoryReference(
                memory_id=result.memory_id,
                summary=_summarize(result.content),
                confidence=result.confidence,
            )
            for result in parsed.results
        ]

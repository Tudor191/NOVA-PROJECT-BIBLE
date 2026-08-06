"""AI Model Orchestration Engine event payloads (Bible Part 7), per
docs/design/phase-2a/00-ai-model-orchestration-engine.md §13 (event flow) and
§14 (served RPCs).

Every payload here carries `schema_version: int = 1` from its first commit
(ADR-024) -- this is the first engine built after that ADR, so there is no
retrofitting question the way there was for Phase 1's Memory/Knowledge/World
Model payloads.

`ContextComponentPayload`/`ToolSchemaPayload`/`ToolCallPayload` mirror
`nova_ai_model_orchestration_engine.domain.models`'s shapes of the same name
but are defined independently here, the same one-way dependency direction
every other engine's wire payloads follow (nova-contracts has no dependency
on any engine's own domain layer).

`PrivacyLevel` is reused from `nova_contracts.events.memory`, not redefined --
the same shared-classification convention every engine follows (docs/design/
phase-1/00-shared-foundations.md).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nova_contracts.events.memory import PrivacyLevel
from nova_contracts.registry import register_payload

_AUDIO_BYTES_CONFIG = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")
"""Pydantic v2's default JSON handling for `bytes` fields requires valid UTF-8
and raises on arbitrary binary content -- audio is never valid UTF-8 in
general, so every payload carrying raw audio must set this explicitly (mirrors
`nova_ai_model_orchestration_engine.domain.models._AUDIO_BYTES_CONFIG`, defined
independently here per this module's own one-way-dependency convention)."""


class RequestOutcome(StrEnum):
    """Mirrors `UsageRecord.outcome` (design doc §4) -- a closed set describing
    how a routed request concluded, independent of the connector-specific
    reason why."""

    SUCCESS = "success"
    FALLBACK = "fallback"
    FAILED = "failed"


class ModelHealthStatus(StrEnum):
    """Mirrors `ModelDescriptor.health_status` (design doc §4)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class BudgetScope(StrEnum):
    """Mirrors `Budget.scope` (design doc §4) -- what a spending limit applies to."""

    GLOBAL = "global"
    PROVIDER = "provider"
    MODEL = "model"


class ContextComponentPayload(BaseModel):
    """One pre-assembled, source-labeled block of context (design doc §0) --
    this engine formats and fits these into a model's window; it never sources
    them."""

    source: str
    text: str
    token_estimate: int
    priority: int = 0
    truncation_policy: Literal["drop", "truncate_end", "summarize_external"] = "truncate_end"


class ToolSchemaPayload(BaseModel):
    """A tool's name/description/parameters, supplied by the caller (design doc
    §0's Function Registry boundary) -- this engine translates it into a
    provider's wire format and back; it never knows what the tool does."""

    name: str
    description: str
    parameters_json_schema: dict[str, Any]


class ToolCallPayload(BaseModel):
    """A normalized tool-call request from a model's response, identical in
    shape regardless of which connector produced it (ADR-023)."""

    id: str
    tool_name: str
    arguments: dict[str, Any]


@register_payload("ai_model.generate.request")
class GenerateRequestPayload(BaseModel):
    """Event Bus RPC counterpart to `POST /v1/models/generate` (design doc §13,
    §14) -- for callers that prefer request/reply over HTTP."""

    context: list[ContextComponentPayload]
    tools: list[ToolSchemaPayload] = Field(default_factory=list)
    task_type: str = "general_conversation"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID
    preferred_model_id: UUID | None = None
    max_output_tokens: int | None = None
    schema_version: int = 1


@register_payload("ai_model.generate.reply")
class GenerateReplyPayload(BaseModel):
    text: str
    tool_calls: list[ToolCallPayload] = Field(default_factory=list)
    input_tokens: int
    output_tokens: int
    finish_reason: Literal["stop", "length", "tool_calls", "error"]
    structural_confidence: float
    model_id: UUID
    provider: str
    error: str | None = None
    """Set only when `finish_reason == "error"` (the fallback chain was
    exhausted) -- an informative reply, not a bus timeout with no diagnostic
    (added additively per ADR-024; `None` for every ordinary reply)."""
    schema_version: int = 1


@register_payload("ai_model.embed.request")
class EmbedRequestPayload(BaseModel):
    """Event Bus RPC counterpart to `POST /v1/models/embed` (design doc §10)."""

    texts: list[str]
    requesting_engine: str
    correlation_id: UUID
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    preferred_model_id: UUID | None = None
    schema_version: int = 1


@register_payload("ai_model.embed.reply")
class EmbedReplyPayload(BaseModel):
    embeddings: list[list[float]]
    model_id: UUID
    provider: str
    error: str | None = None
    """Set only when embedding failed (the fallback chain was exhausted) --
    `embeddings` is empty in that case (added additively per ADR-024)."""
    schema_version: int = 1


@register_payload("ai_model.transcribe.request")
class TranscribeRequestPayload(BaseModel):
    """Event Bus RPC for speech-to-text (docs/design/phase-2d/
    01-communication-engine.md §0.3) -- `communication-engine`'s only legal path
    to a speech provider, per ADR-020. Non-streaming: transcription operates on
    one bounded utterance per call (the caller decides utterance boundaries via
    its own Transport VAD), never a transport-level stream."""

    model_config = _AUDIO_BYTES_CONFIG

    audio_bytes: bytes
    audio_format: Literal["wav", "opus", "pcm16"] = "wav"
    language_hint: str | None = None
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("ai_model.transcribe.reply")
class TranscribeReplyPayload(BaseModel):
    text: str
    detected_language: str | None = None
    structural_confidence: float
    model_id: UUID
    provider: str
    error: str | None = None
    """Set only when transcription failed (the fallback chain was exhausted) --
    `text` is empty in that case (added additively per ADR-024)."""
    schema_version: int = 1


@register_payload("ai_model.synthesize.request")
class SynthesizeRequestPayload(BaseModel):
    """Event Bus RPC for text-to-speech (docs/design/phase-2d/
    01-communication-engine.md §0.3). Non-streaming, the same reason as
    `TranscribeRequestPayload` -- `EventBus.request()` returns a single
    `EventEnvelope`, never a stream (per `nova_ai_model_orchestration_engine.
    domain.ports.ModelConnector.synthesize_stream`'s own docstring).
    `communication-engine` achieves perceived streaming by calling this RPC
    once per response chunk (sentence/phrase), not by streaming one call."""

    text: str
    voice_profile: str | None = None
    audio_format: Literal["wav", "opus", "pcm16"] = "wav"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID
    schema_version: int = 1


@register_payload("ai_model.synthesize.reply")
class SynthesizeReplyPayload(BaseModel):
    model_config = _AUDIO_BYTES_CONFIG

    audio_bytes: bytes
    audio_format: Literal["wav", "opus", "pcm16"]
    structural_confidence: float
    model_id: UUID
    provider: str
    error: str | None = None
    """Set only when synthesis failed (the fallback chain was exhausted) --
    `audio_bytes` is empty in that case (added additively per ADR-024)."""
    schema_version: int = 1


@register_payload("ai_model.request.completed")
class RequestCompletedPayload(BaseModel):
    """Published after every successful (including fallback-recovered) request
    -- the event-bus mirror of the `usage_record` row `UsageRepository.
    record_usage` persists (ADR-021's mandated structured telemetry)."""

    correlation_id: UUID
    requesting_engine: str
    provider: str
    model_id: UUID
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: float
    retry_count: int = 0
    fallback_used: bool = False
    outcome: RequestOutcome
    schema_version: int = 1


@register_payload("ai_model.request.failed")
class RequestFailedPayload(BaseModel):
    """Published when the fallback chain is exhausted with no candidate left
    to try (design doc §7, §17)."""

    correlation_id: UUID
    requesting_engine: str
    attempted_model_ids: list[UUID]
    final_error: str
    schema_version: int = 1


@register_payload("ai_model.model.registered")
@register_payload("ai_model.model.deregistered")
class ModelRegistryChangedPayload(BaseModel):
    """Shared shape for `.registered`/`.deregistered` -- the two subjects differ
    only in when they fire, the same convention as World Model's `WorldObjectChangedPayload`."""

    model_id: UUID
    name: str
    provider: str
    schema_version: int = 1


@register_payload("ai_model.model.health_changed")
class ModelHealthChangedPayload(BaseModel):
    model_id: UUID
    previous_status: ModelHealthStatus
    new_status: ModelHealthStatus
    schema_version: int = 1


@register_payload("ai_model.budget.exceeded")
class BudgetExceededPayload(BaseModel):
    scope: BudgetScope
    scope_ref: str | None = None
    limit_amount: float
    current_spend: float
    schema_version: int = 1

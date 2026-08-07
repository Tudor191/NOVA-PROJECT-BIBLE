"""Domain entities -- not ORM models (docs/design/phase-2a/00-ai-model-orchestration-engine.md
§1). `PrivacyLevel` is re-exported from `nova_contracts.events.memory` rather than
redefined here, the same shared-classification convention every Phase 1 engine
already follows.

**The boundary this file exists to enforce** (Bible Part 7's "Architectural
Requirements", ADR-020, ADR-022): this engine is a stateless intelligence-provider
gateway. Every model here is either a request/response shape for a single,
self-contained call, or a registry/telemetry record about *models themselves* --
never a conversation, a memory, a fact, or a snapshot of reality. If a future change
to this file would make it hold a caller's conversation history, a cached "what we
discussed last time," or an opinion about what a tool call's result *means*, it
belongs in a different engine instead (Memory, Knowledge, World Model, or the future
Reasoning Engine, respectively).

`ContextComponent` is the concrete embodiment of the Prompt Pipeline / Context
Builder boundary (design doc §0): it carries already-decided content plus enough
metadata to format and truncate it correctly, never a pointer this engine would
have to resolve by calling another engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from nova_contracts.events.memory import PrivacyLevel
from pydantic import BaseModel, ConfigDict, Field

_AUDIO_BYTES_CONFIG = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")
"""Pydantic v2's default JSON handling for `bytes` fields requires valid UTF-8
and raises `PydanticSerializationError` on arbitrary binary content (confirmed
empirically while building this module: `b'\\x00\\x01\\xff...'.model_dump_json()`
fails without this). Every model carrying raw audio must set this explicitly --
audio is never valid UTF-8 in general, unlike every other `bytes`-free model in
this codebase, which is why this is a new, audio-specific concern, not a change
to any existing model."""

__all__ = [
    "AudioChunk",
    "Budget",
    "CapabilityDimension",
    "CapabilityScores",
    "ConnectorHealth",
    "ContextComponent",
    "FaceEmbedRequest",
    "FaceEmbedResult",
    "GazeEstimateRequest",
    "GazeEstimateResult",
    "GenerateChunk",
    "GenerateRequest",
    "GenerateResult",
    "Modality",
    "ModelDescriptor",
    "PrivacyLevel",
    "RoutingDecision",
    "ScoredCandidate",
    "SynthesizeRequest",
    "SynthesizeResult",
    "ToolCall",
    "ToolSchema",
    "TranscribeRequest",
    "TranscribeResult",
    "UsageRecord",
    "VoiceEmbedRequest",
    "VoiceEmbedResult",
    "WakePhraseRequest",
    "WakePhraseResult",
]

# Bible Part 7 "Model Capability Matrix" -- the twelve scored dimensions, plus
# two added per docs/design/phase-2d/01-communication-engine.md §0.3 (speech),
# plus four added per docs/design/phase-2d/03-perception-engine.md §0.2
# (biometric/wake): the existing generic "speech"/"vision" dimensions score a
# text-generation model's general aptitude with speech/vision-related
# conversation topics (Part 7's original twelve); they are not a substitute for
# scoring a *dedicated* connector's actual capability at one narrow task, which
# is what routing a `speech_to_text`/`wake_phrase_detection`/`voice_embedding`/
# `face_embedding`/`gaze_estimation` request actually needs to compare
# purpose-built candidates against each other.
CapabilityDimension = Literal[
    "general_conversation",
    "programming",
    "reasoning",
    "mathematics",
    "translation",
    "vision",
    "speech",
    "planning",
    "creativity",
    "research",
    "tool_usage",
    "long_context",
    "speech_recognition_accuracy",
    "speech_synthesis_quality",
    "wake_phrase_detection_accuracy",
    "voice_embedding_quality",
    "face_embedding_quality",
    "gaze_estimation_accuracy",
]

Modality = Literal[
    "text_generation",
    "streaming",
    "embedding",
    "tool_calling",
    "speech_to_text",
    "text_to_speech",
    "wake_phrase_detection",
    "voice_embedding",
    "face_embedding",
    "gaze_estimation",
]
HealthStatus = Literal["healthy", "degraded", "unhealthy", "unknown"]


class CapabilityScores(BaseModel):
    """Per-model scores, one per Part 7 capability dimension, each in [0, 1]."""

    scores: dict[CapabilityDimension, float] = Field(default_factory=dict)

    def score_for(self, dimension: CapabilityDimension) -> float:
        return self.scores.get(dimension, 0.0)


class ModelDescriptor(BaseModel):
    """One `model_registry` row (Part 7's "central catalog of intelligence
    providers"). `id` is the registry's own surrogate key -- distinct from
    `name`/`version`/`provider`, which together are the natural key."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str
    provider: str
    connector_type: str
    is_local: bool
    modalities: list[Modality]
    capability_scores: CapabilityScores
    context_window: int
    max_output_tokens: int
    avg_latency_ms: float | None = None
    avg_quality_score: float | None = None
    hardware_requirements: dict[str, str] = Field(default_factory=dict)
    license: str | None = None
    cost_per_input_token: float | None = None
    cost_per_output_token: float | None = None
    max_privacy_tier: PrivacyLevel = PrivacyLevel.INTERNAL
    """The highest (most sensitive) privacy tier this model is permitted to serve
    (Part 7 "Privacy Management"). A local model is typically registered with this
    set to `HIGHLY_SENSITIVE` (it's inherently safe -- nothing leaves the device);
    a cloud model defaults to `INTERNAL` until explicitly cleared for more, and per
    the design doc §18 a `HIGHLY_SENSITIVE` request is never eligible for a model
    whose ceiling is lower, with no override."""
    health_status: HealthStatus = "unknown"
    schema_version: int = 1  # ADR-024


class ConnectorHealth(BaseModel):
    available: bool
    latency_ms: float | None = None
    error_rate: float | None = None
    detail: str | None = None


class ContextComponent(BaseModel):
    """One named, pre-assembled block of context (design doc §0): this engine
    formats and fits these into a model's window -- it never sources them. `source`
    is a free-text label the caller chooses (e.g. "memory", "knowledge",
    "world_model", "system_identity") purely for telemetry/explainability (ADR-021);
    this engine attaches no special behavior to any particular value."""

    source: str
    text: str
    token_estimate: int
    priority: int = 0  # higher survives truncation first
    truncation_policy: Literal["drop", "truncate_end", "summarize_external"] = "truncate_end"


class ToolSchema(BaseModel):
    """A tool's name/description/parameters, supplied per-request by the caller
    (design doc §0's Function Registry) -- this engine translates it into a
    provider's wire format and back; it never knows what the tool does."""

    name: str
    description: str
    parameters_json_schema: dict


class ToolCall(BaseModel):
    """A normalized tool-call request from a model's response, identical in shape
    regardless of which connector produced it (ADR-023)."""

    id: str
    tool_name: str
    arguments: dict


class GenerateRequest(BaseModel):
    context: list[ContextComponent]
    tools: list[ToolSchema] = Field(default_factory=list)
    task_type: str = "general_conversation"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    preferred_model_id: UUID | None = None
    max_output_tokens: int | None = None
    schema_version: int = 1  # ADR-024


class GenerateResult(BaseModel):
    text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    input_tokens: int
    output_tokens: int
    finish_reason: Literal["stop", "length", "tool_calls", "error"]
    structural_confidence: float
    """Mechanical confidence -- did the response come back well-formed, was a
    fallback needed -- never semantic/content quality, which is Reasoning Engine's
    concern (design doc §7 "Validate Output")."""


class GenerateChunk(BaseModel):
    delta_text: str = ""
    tool_call_delta: ToolCall | None = None
    finished: bool = False
    finish_reason: Literal["stop", "length", "tool_calls", "error"] | None = None


class TranscribeRequest(BaseModel):
    """Speech-to-text (design doc §0.3). `audio_bytes` carries the raw audio for
    one bounded utterance -- this engine transcribes what it's given in one
    call; deciding how to chunk a longer stream into utterance-sized calls is
    `communication-engine`'s job (Transport VAD), never this engine's, the same
    "formats/fits what it's given, never sources it" boundary `ContextComponent`
    already enforces for text."""

    model_config = _AUDIO_BYTES_CONFIG

    audio_bytes: bytes
    audio_format: Literal["wav", "opus", "pcm16"] = "wav"
    language_hint: str | None = None
    """ISO 639-1 code, optional (design doc §0.1's multilingual-input scope) --
    a hint the connector may use to skip language auto-detection, never a
    requirement; an unrecognized or omitted hint falls back to
    auto-detection."""
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1  # ADR-024


class TranscribeResult(BaseModel):
    text: str
    detected_language: str | None = None
    structural_confidence: float
    """Mechanical confidence only (mirrors `GenerateResult`'s field) -- did the
    connector return a well-formed transcript, never a semantic judgment about
    whether the transcript is what the user meant."""


class SynthesizeRequest(BaseModel):
    """Text-to-speech (design doc §0.3). One already-personality-validated
    response string in -- this engine never decides *what* to say, only
    renders it to audio, the same content/rendering boundary `generate` already
    keeps against Reasoning Engine's content."""

    text: str
    voice_profile: str | None = None
    """Connector-specific voice identifier, optional -- `None` selects the
    connector's own default voice; this engine attaches no meaning to the
    value beyond passing it through (mirrors `ContextComponent.source`'s
    opaque-label convention)."""
    audio_format: Literal["wav", "opus", "pcm16"] = "wav"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1  # ADR-024


class SynthesizeResult(BaseModel):
    model_config = _AUDIO_BYTES_CONFIG

    audio_bytes: bytes
    audio_format: Literal["wav", "opus", "pcm16"]
    structural_confidence: float


class AudioChunk(BaseModel):
    """One incremental piece of synthesized audio, HTTP/SSE-streaming only --
    never an Event Bus contract, the same boundary `GenerateChunk`'s streaming
    already keeps (design doc §0.3, mirroring `api/generate.py`'s existing
    `POST /generate/stream`). Engine-to-engine callers (`communication-engine`,
    per ADR-004) use the non-streaming `synthesize` RPC and achieve perceived
    streaming by calling it per response-chunk (sentence/phrase) rather than by
    streaming a single call's transport."""

    model_config = _AUDIO_BYTES_CONFIG

    delta_audio_bytes: bytes = b""
    finished: bool = False


class WakePhraseRequest(BaseModel):
    """Wake-phrase detection (docs/design/phase-2d/03-perception-engine.md
    §0.2). `audio_bytes` carries one bounded audio window -- `perception-engine`
    decides windowing (its own presence/motion-gated cadence, §7.2 of that
    document), this engine detects what's given, the same "formats/fits what
    it's given, never sources it" boundary `TranscribeRequest` already keeps."""

    model_config = _AUDIO_BYTES_CONFIG

    audio_bytes: bytes
    audio_format: Literal["wav", "opus", "pcm16"] = "wav"
    wake_phrase: str | None = None
    """Connector-specific phrase identifier, optional -- `None` selects the
    connector's own configured default phrase."""
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1  # ADR-024


class WakePhraseResult(BaseModel):
    matched: bool
    structural_confidence: float
    """Mechanical confidence only (mirrors `TranscribeResult`'s field) -- did
    the connector return a well-formed detection, never a semantic judgment
    about whether the phrase was genuinely directed at NOVA (that fusion is
    perception-engine's own job, never this engine's, per ADR-020's "this
    engine renders no judgment about content" boundary)."""


class VoiceEmbedRequest(BaseModel):
    """Voiceprint extraction (docs/design/phase-2d/03-perception-engine.md
    §0.2). One bounded audio sample in, one fixed-length embedding out --
    matching against enrolled templates is `perception-engine`'s own job
    (its `domain/identity_fusion.py`), never this engine's, mirroring how this
    engine renders audio to speech but never decides *what* to say."""

    model_config = _AUDIO_BYTES_CONFIG

    audio_bytes: bytes
    audio_format: Literal["wav", "opus", "pcm16"] = "wav"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1  # ADR-024


class VoiceEmbedResult(BaseModel):
    embedding: list[float]
    structural_confidence: float


class FaceEmbedRequest(BaseModel):
    """Faceprint extraction (docs/design/phase-2d/03-perception-engine.md
    §0.2). `image_bytes` carries one already-detected face crop, never a full
    frame -- face detection itself is this connector's own concern (mirrors
    `TranscribeRequest`'s "caller decides utterance boundaries" boundary,
    applied here to face-region boundaries instead)."""

    model_config = _AUDIO_BYTES_CONFIG

    image_bytes: bytes
    image_format: Literal["jpeg", "png"] = "jpeg"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1  # ADR-024


class FaceEmbedResult(BaseModel):
    embedding: list[float]
    structural_confidence: float


class GazeEstimateRequest(BaseModel):
    """Gaze/attention estimation (docs/design/phase-2d/03-perception-engine.md
    §0.2). `image_bytes` carries one already-detected face crop, the same
    boundary as `FaceEmbedRequest`."""

    model_config = _AUDIO_BYTES_CONFIG

    image_bytes: bytes
    image_format: Literal["jpeg", "png"] = "jpeg"
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL
    requesting_engine: str
    correlation_id: UUID = Field(default_factory=uuid4)
    schema_version: int = 1  # ADR-024


class GazeEstimateResult(BaseModel):
    gaze_direction: Literal["toward_device", "away", "unknown"]
    structural_confidence: float


class ScoredCandidate(BaseModel):
    """One candidate's score breakdown (ADR-021) -- part of `RoutingDecision`."""

    model_id: UUID
    capability_score: float
    cost_score: float
    latency_score: float
    historical_success_rate: float | None
    composite_score: float


class RoutingDecision(BaseModel):
    """The structured, reproducible explanation for a routing choice (ADR-021).
    `explanation` is derived from the fields below, never authored independently,
    so it can never claim something the structured data doesn't support."""

    candidates: list[ScoredCandidate]
    selected_model_id: UUID
    fallback_from: UUID | None = None
    privacy_constraint_applied: bool
    estimated_complexity: float
    """0.0-1.0, from the structural heuristic (design doc §7) -- never an LLM-driven
    estimate, which would be circular."""
    explanation: str


class UsageRecord(BaseModel):
    """The structured telemetry record mandated for every request, success or
    failure (ADR-021) -- exactly the fields named: provider, model, routing reason,
    complexity, latency, tokens, cost, retry count, fallback usage, privacy
    classification."""

    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID
    requesting_engine: str
    provider: str
    model_id: UUID
    routing_decision: RoutingDecision
    estimated_complexity: float
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    retry_count: int
    fallback_used: bool
    privacy_classification: PrivacyLevel
    outcome: Literal["success", "fallback", "failed"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = 1  # ADR-024


class Budget(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    scope: Literal["global", "provider", "model"]
    scope_ref: str | None = None
    period: Literal["monthly"] = "monthly"
    limit_amount: float
    currency: str = "USD"
    alert_threshold_pct: int = 80

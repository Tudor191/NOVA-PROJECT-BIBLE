"""Communication Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COMMUNICATION_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `communication` schema (ORM, Alembic) --
    conversation sessions, turns, notifications, and the transactional
    outbox (design doc Sec10)."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's own job queue backend only (`workers/outbox_worker.py`) -- the
    same convention every prior engine's `config.py` follows."""

    communication_engine_vad_end_of_utterance_silence_ms: float = 700.0
    """Design doc Sec4 -- `domain.vad.TransportVadConfig`'s own default,
    overridable per deployment without a code change."""

    communication_engine_personality_rpc_timeout_ms: int = 2000
    """Design doc Sec7 step 2, Sec9 -- how long the intent gate waits on
    `personality.validate_response` before applying the degraded-mode
    fallback (deliver unvalidated, `personality_validated=false`)."""

    communication_engine_world_model_rpc_timeout_ms: int = 2000
    """Design doc Sec8.7 -- the one `world_model.context.request` call made
    at session creation."""

    communication_engine_synthesize_rpc_timeout_ms: int = 5000
    """Design doc Sec0.3, Sec8.1 -- per-chunk `ai_model.synthesize` timeout;
    longer than the other two since TTS synthesis genuinely takes longer
    than a lookup RPC."""

    communication_engine_transcribe_rpc_timeout_ms: int = 5000
    """Design doc Sec0.3, Sec8.1 -- `ai_model.transcribe` timeout."""

    communication_engine_reasoning_rpc_timeout_ms: int = 10000
    """Closure doc (05-conversation-intelligence-closure.md) Sec5, Priority
    3 -- how long `conversation_orchestration.handle_conversation_turn`
    waits on `reasoning.reason.request` before falling back to
    `FALLBACK_CONTENT`. Longer than the other RPC timeouts above: unlike a
    lookup or a single transcription/synthesis call, reasoning-engine's own
    pipeline may itself call memory/knowledge/world-model/ai-model before
    returning."""

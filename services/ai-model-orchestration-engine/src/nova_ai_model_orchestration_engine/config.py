"""AI Model Orchestration Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AI_MODEL_ORCHESTRATION_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `model_orchestration` schema (ORM, Alembic)."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's own job queue backend only (`workers/__init__.py`) -- this engine has
    no domain use for Redis of its own (ADR-022: the only permitted in-process
    state is the registry/capability-matrix cache, never an external store),
    the same "Arq needs it regardless" precedent as Knowledge Engine's own
    `config.py`."""

    ollama_base_url: str = "http://localhost:11434"
    """The default, zero-budget connector's endpoint (Part 7 "Initial Zero Budget
    Strategy") -- the same Ollama server Memory/Knowledge Engine's own (soon to
    migrate, per ADR-020's Future Implications) embedding calls already target."""

    anthropic_api_key: str = ""
    """Empty by default. `connectors/factory.py` only constructs an
    `AnthropicConnector` when this is set -- a cloud connector with no configured
    credential is simply absent from the live connector set, not a runtime
    surprise at first request (§18's API key handling)."""

    connector_timeout_s: float = 60.0

    health_check_interval_seconds: int = 30
    """`workers/health_monitor_worker.py`'s fixed poll interval (§2) -- Phase 2A's
    own accepted fixed-interval tradeoff, the same one every Phase 1 worker
    makes."""

    benchmark_interval_hours: int = 24
    """`workers/benchmark_worker.py`'s fixed cycle (§2), matching Memory Engine's
    `consolidation_interval_hours` precedent."""

"""Planning Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLANNING_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `planning` schema (ORM, Alembic) --
    `task_graph`/`task_node`/`outbox_event`
    (`phase-3b-planning-persistence` precursor, TDD 3B §4)."""

    outbox_dispatch_batch_size: int = 100
    """Matches `nova_service_kit.outbox.DEFAULT_BATCH_SIZE` -- overridable
    per-engine, the same pattern `memory-engine`'s own worker settings use."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's broker for `workers/outbox_worker.py` (`WorkerSettings.redis_settings`)
    -- matches `memory-engine`'s own default."""

    decomposition_confidence_threshold: float = 0.6
    """Fork 3B-3 (docs/design/phase-3/05-tdd-3b-planning-engine.md §7):
    `reasoning.process.completed` below this `confidence_score` is not
    decomposed. Reuses `reasoning-engine`'s own `DEFAULT_VERIFY_THRESHOLD`
    value rather than inventing a second, arbitrary constant -- the TDD's
    own proposal, not silently assumed: flagged as an unconfirmed default
    in this unit's Gate Review, not yet given an explicit numeric approval
    by name."""

    decomposition_model_orchestration_timeout_ms: int = 10_000
    """Passed to `ModelOrchestrationClient` -- matches `reasoning-engine`'s
    own default for the same RPC (generation calls are slow)."""

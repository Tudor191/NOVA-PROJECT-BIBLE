"""Reasoning Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REASONING_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `reasoning` schema (ORM, Alembic) -- §20's
    one narrow exception to "never owns data": records of this engine's own
    reasoning processes only."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's own job queue backend only (`workers/outbox_worker.py`) -- this
    engine has no other domain use for Redis, the same "Arq needs it
    regardless" precedent as every prior engine's own `config.py`."""

    confidence_verify_threshold: float = 0.6
    """§10, §18: passed to `domain.pipeline.run`'s `verify_threshold`."""

    confidence_override_threshold: float = 0.35
    """§10, §18: passed to `domain.pipeline.run`'s `override_threshold`."""

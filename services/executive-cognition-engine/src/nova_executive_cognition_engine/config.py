"""Executive Cognition Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EXECUTIVE_COGNITION_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `executive` schema (ORM, Alembic) --
    design doc §19's one narrow exception to "never owns data": records of
    this engine's own arbitration decisions only."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's own job queue backend only (`workers/outbox_worker.py`) -- this
    engine has no other domain use for Redis, the same precedent every
    prior engine's own `config.py` follows."""

    executive_engine_resource_budget_ceiling: float = 1.0
    """Design doc §7 step 5, §20 -- a `Settings`-tunable ceiling on
    cumulative `resource_cost` per arbitration round, passed to
    `domain.arbitration.arbitrate`."""

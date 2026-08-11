"""digital-twin-engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md Sec6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DIGITAL_TWIN_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `digital_twin` schema (ORM, Alembic)."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's own job queue backend only (`workers/__init__.py`) -- outbox
    dispatch, per every prior publishing engine's own convention."""

    trust_metric_window_size: int = 20
    """Sec9's own rolling window -- "an implementation-time parameter, not
    an architectural fork," e.g. last 20 completed sessions. Recomputed
    from `list_recent_completed_sessions` every time a new
    `communication.session.completed` event arrives."""

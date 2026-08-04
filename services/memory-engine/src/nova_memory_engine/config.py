"""Memory Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMORY_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `memory` schema (ORM, Alembic). The
    `nova-vectorstore-sdk` pgvector backend needs the same database without the
    `+asyncpg` dialect qualifier -- see `main.py`'s `vector_store_dsn()`, a derived
    value rather than a second setting that could drift from this one."""

    redis_url: str = "redis://localhost:6379/0"

    embedding_model: str = "nomic-embed-text"  # ADR-010

    consolidation_interval_hours: int = 6
    """docs/design/phase-1/01-memory-engine.md §6: fixed interval for Phase 1: a
    real idle-time scheduler is Phase 4's Cognitive State Engine."""

    short_term_expiry_check_interval_minutes: int = 15

    def vector_store_dsn(self) -> str:
        return self.postgres_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

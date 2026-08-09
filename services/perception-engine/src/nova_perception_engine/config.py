"""Perception Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md Sec6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PERCEPTION_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `perception` schema (ORM, Alembic)."""

    redis_url: str = "redis://localhost:6379/0"
    """Arq's own job queue backend only (`workers/__init__.py`) -- this
    engine has no domain use for Redis of its own."""

    template_encryption_key: str = ""
    """Base64-encoded Fernet key for `domain/enrollment.py`'s application-
    level template encryption (docs/design/phase-2d/03-perception-engine.md
    Sec11) -- managed outside this engine's own schema per standard
    secrets-management practice. Empty by default in this dev-mode default
    only so the engine still boots for read-only endpoints without a key
    configured; enrollment fails explicitly (never silently) if this is
    unset when actually called."""

    correlation_window_seconds: float = 2.5
    """Sec17's continuous-reassessment cadence -- a new correlation window
    every 2-3 seconds while a presence session is active, a starting
    parameter tuned by Sec20's calibration tests, not a fixed constant."""

    ai_model_orchestration_timeout_ms: int = 5000
    """Event-Bus request/reply timeout for the four biometric/wake RPCs
    (Sec0.2) -- `clients/ai_model_orchestration_client.py`."""

    primary_user_id: UUID | None = None
    """Closure Priority 2 (docs/design/phase-2d/
    05-conversation-intelligence-closure.md Sec4) -- the deployment's
    single trusted user (ADR-025's Personal Edition default), a scoped
    stopgap for the not-yet-built `current_principal`/device-keypair
    mechanism (docs/architecture/13-auth-and-security.md). Empty by
    default, mirroring `template_encryption_key`'s pattern: the engine
    still boots and serves presence-only observations without it configured,
    but `observation_orchestration.py::handle_observation_window` degrades
    explicitly (publishes nothing, logs a warning) rather than guessing a
    user identity whenever it is unset -- never a silent fallback."""

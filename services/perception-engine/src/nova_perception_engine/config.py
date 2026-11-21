"""Perception Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md Sec6)."""

from __future__ import annotations

from pathlib import PurePosixPath
from uuid import UUID

from pydantic import field_validator
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

    workspace_debounce_seconds: float = 1.0
    """Phase 4F.2 (TDD 4F §9's *"debounce and coalesce high-frequency OS
    signals"*). One editor save emits several filesystem events within a few
    hundred milliseconds; one second collapses that burst while leaving two
    genuinely separate edits distinguishable.

    **Well inside AC-7's 5-second budget**, and deliberately so: debouncing
    delays the first observation of an object by nothing at all -- the first
    is always admitted -- so this spends no part of that budget on the path
    AC-7 measures."""

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

    project_folder_bindings: dict[str, UUID] = {}
    """Phase 4F.8, A-4F8-2 (a), ratified 2026-10-11 (TDD 4F.8 §29.1). The
    operator's declaration of which folder belongs to which project: an absolute
    folder path, as `nova-companion` reports paths, mapped to a project
    identity. Set as JSON, e.g.
    `PERCEPTION_ENGINE_PROJECT_FOLDER_BINDINGS='{"/workspace/atlas": "<uuid>"}'`.

    **Empty by default**, so nothing is a known project until an operator says
    so. A location is declared, never inferred.

    **A binding is inert until its project identity has been seen** on
    `memory.long_term.created` (`perception.known_project`). Declaring a folder
    for a project NOVA does not hold makes nothing known."""

    @field_validator("project_folder_bindings")
    @classmethod
    def _bindings_name_absolute_folders(cls, value: dict[str, UUID]) -> dict[str, UUID]:
        """Normalized to one spelling per folder, and refused unless absolute: a
        relative folder would match against whatever the companion's working
        directory happened to be."""
        normalized: dict[str, UUID] = {}
        for folder, project_id in value.items():
            path = PurePosixPath(folder.strip())
            if not path.is_absolute() or path == PurePosixPath("/"):
                raise ValueError(
                    f"a project folder binding must name an absolute folder below /: {folder!r}"
                )
            normalized[str(path)] = project_id
        return normalized

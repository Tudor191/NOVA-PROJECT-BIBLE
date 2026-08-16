"""Capability Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CAPABILITY_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `capability` schema (ORM, Alembic) --
    the registry and the append-only installation-event log
    (docs/design/phase-3/06-tdd-3c-capability-engine.md §6)."""

    sandbox_filesystem_root: str = "/workspace"
    """The `filesystem`/`git` built-ins' declared allow-list root (TDD 3C
    §3) -- deployment-scoped, not hardcoded in the manifest itself."""

    sandbox_terminal_allowed_executables: list[str] = ["git", "python3", "pytest", "ruff", "uv"]
    """The `terminal` built-in's declared executable allow-list (TDD 3C §3)."""

    sandbox_http_allowed_hosts: list[str] = []
    """The `http` built-in's declared outbound-host allow-list (TDD 3C §3)
    -- empty by default; every deployment that wants the `http` capability
    usable must configure this explicitly (fail-closed, the same idiom
    `digital-twin-engine`'s `ProactiveBoundaryPolicy` established for an
    absent policy)."""

    sandbox_terminal_timeout_s: float = 30.0
    sandbox_http_timeout_s: float = 10.0

    primary_user_id: UUID | None = None
    """The single trusted user this instance's Permission Review
    disclosure (TDD 3C §5, ADR-025's single-trusted-user-per-instance
    assumption) targets -- unset means the disclosure is skipped, not
    silently sent nowhere (same convention as `perception-engine`'s own
    `Settings.primary_user_id`)."""

    communication_rpc_timeout_ms: int = 2000
    """How long the Permission Review pipeline stage waits on
    `communication.session.lookup_by_user.request`/
    `communication.intent.deliver.request` before treating the disclosure
    as a timeout (never a pipeline failure -- best-effort, TDD 3C §5)."""

"""Registry configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_OS_REGISTRY_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"
    postgres_dsn: str = "postgresql+asyncpg://nova:nova@localhost:5432/nova"
    agents_root: str = "agents"
    """Doc 02's `agents/` directory -- Phase 3's sole, filesystem-based
    discovery root (doc 12 §6/§15). Relative paths are resolved against
    the process's current working directory, matching every other
    engine's own relative-path settings convention."""
    kernel_version: str = "0.1.0"
    """No Kernel-version-discovery RPC exists yet -- a disclosed, minimal
    stand-in matching `agent-os/kernel`'s own current
    `FastAPI(..., version="0.1.0")` literal exactly (Phase 3E Milestone
    2). Not a new architecture: no new event/RPC contract is invented
    here."""
    primary_user_id: UUID | None = None
    """ADR-025's single-trusted-user-per-instance assumption,
    `capability-engine`'s own `Settings.primary_user_id` precedent --
    the Permission Review stage's best-effort delivery target."""

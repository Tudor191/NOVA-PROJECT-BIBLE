"""Kernel configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_OS_KERNEL_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"
    postgres_dsn: str = "postgresql+asyncpg://nova:nova@localhost:5432/nova"
    agents_root: str = "agents"
    """Doc 02's `agents/` directory -- the Kernel Scheduler's own dynamic-
    import root for a dispatched instance's `src/handler.py` (TDD 3E §4 step
    3-4), mirroring `agent-os/registry`'s own `Settings.agents_root`
    identically (both resolve relative paths against the process's current
    working directory)."""
    primary_user_id: UUID | None = None
    """ADR-025's single-trusted-user-per-instance assumption,
    `capability-engine`/`registry`/`supervisors`' own
    `Settings.primary_user_id` precedent. Disclosed addition: the Kernel
    Scheduler needs a `user_id` to construct `AgentContext.world_model_slice`
    (`WorldModelSnapshot.user_id` is a required field) -- no World Model
    Engine RPC is called for this in Phase 3 (`degraded=True` is always set,
    the same "proceed without... reduced-confidence grounding" semantics
    `ContextReplyPayload.degraded` already establishes), so a dispatch with
    `primary_user_id` unset fails loudly rather than synthesizing a fake
    user id."""

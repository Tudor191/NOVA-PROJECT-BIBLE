"""Supervisors configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_OS_SUPERVISORS_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"
    primary_user_id: UUID | None = None
    """ADR-025's single-trusted-user-per-instance assumption,
    `capability-engine`/`registry`'s own `Settings.primary_user_id`
    precedent -- the `user_id` conflict-escalation-to-`reasoning-engine`
    calls require (TDD 3E §7's "existing RPC")."""
    peer_review_timeout_ms: int = 30_000
    """TDD 3E §12: "exact timeout policy is a configuration value, not
    hardcoded" -- the Peer Review round's own timeout, distinct from the
    Event Bus's own per-call `timeout_ms` (`EventPublisher.request()`)."""

    # No Postgres schema: TDD 3E §7 (`agent-os/supervisors`) names no
    # persisted state for the Supervisor itself -- restart-survival is
    # already Kernel-owned (`agent_instance` reconciliation, TDD 3E §4/§12,
    # Milestone 2), and a Supervisor's own in-memory bookkeeping (which
    # instances it currently tracks, in-flight peer-review rounds) is
    # meaningless once the process itself has died, the same reasoning
    # `14-3e-agent-os-research.md` §4 gave for rejecting a shared/duplicated
    # persistence store. See `domain/README` note in `main.py`'s own
    # docstring for the full disclosure.

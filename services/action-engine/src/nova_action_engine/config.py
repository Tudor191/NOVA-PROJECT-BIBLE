"""Action Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACTION_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `action` schema (ORM, Alembic) -- the
    action record, pending-approval state machine, append-only execution
    history, and identity-confidence policy
    (docs/design/phase-3/07-tdd-3d-action-engine.md §8)."""

    capability_rpc_timeout_ms: int = 2000
    """`CapabilityPort`'s `capability.resolve.request`/`capability.invoke.request`
    timeout (TDD 3D §2, §6 stages 5/6)."""

    communication_rpc_timeout_ms: int = 2000
    """`CommunicationPort`'s `communication.intent.deliver.request` timeout
    (TDD 3D §4's approval-loop disclosure step)."""

    world_model_rpc_timeout_ms: int = 2000
    """`IdentityPort`'s `world_model.context.request` timeout (TDD 3D §7,
    ADR-032). A timeout is treated as zero confidence -- fails closed,
    never silently bypasses the gate (TDD 3D §10)."""

    approval_timeout_seconds: float = 300.0
    """Default approval-loop timeout (TDD 3D §4): *"No timeout bypass --
    action blocks until a decision or explicit user timeout policy
    fires."* A timeout denies, never auto-approves -- this project's
    standing fail-closed discipline, the same idiom
    `ProactiveBoundaryPolicy` established for an absent policy."""

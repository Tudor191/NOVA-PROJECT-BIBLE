"""Cognitive State Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COGNITIVE_STATE_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `cognitive_state` schema (ORM, Alembic) --
    Bible Part 6's Active Thoughts (TDD 4F §13). One table in 4F.1; Focus is
    derived and Attention Layers are a column, so neither is stored."""

    primary_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    """**The only identity this engine has** -- ADR-025's single trusted user
    per instance.

    `cognitive_state.active_thought` is keyed by `user_id` because the schema
    already is, **not** because 4F introduces multi-user: there is no RBAC
    concept, no role, no group and no permission-derived allow-list anywhere in
    this engine. The default is a fixed sentinel rather than a random value so a
    fresh instance and a restarted one address the same rows -- the same
    reasoning `autonomy-engine` and `digital-twin-engine` both record."""

    focus_capacity: int = 7
    """*"Only a limited number of cognitive processes receive maximum
    computational attention."* (Part 6:145)

    The **limit is the feature**, so it is configuration rather than a constant
    -- but the default is not arbitrary: Part 6 grounds the Focus System in the
    observation that *"Human attention is limited"* (line 141), and seven is the
    classic working-memory bound that observation refers to. It is a starting
    value to be tuned against real load, not a derived result, and TDD 4F §16
    control 5's spirit applies -- the cap must actually exclude something or the
    subsystem does nothing."""

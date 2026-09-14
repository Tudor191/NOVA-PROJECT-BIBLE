"""Autonomy Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTONOMY_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `autonomy` schema (ORM, Alembic) -- the
    autonomy level, policies, permission grants, suggestions, and doc 07's
    append-only `decision_log` (TDD 4D §9)."""

    primary_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    """**The only identity this engine has** -- ADR-025's single trusted user
    per instance, unchanged by 4D (TDD §10 item 5).

    Every `autonomy` table is keyed by `user_id` because the schema already is,
    not because 4D introduces multi-user: there is no RBAC concept, no role, no
    group, and no permission-derived allow-list anywhere in this engine.

    D-3's session is a shared local bearer token (`LocalTokenSessionValidator`)
    that carries **no subject claim**, so there is no user id to inherit from
    the request -- which is exactly why TDD §10 item 5 names this setting as
    the only identity. The default is a fixed sentinel rather than a random
    value so a fresh instance and a restarted one address the same rows."""

    suggestion_page_size: int = 50
    """Default keyset page size for `GET /v1/autonomy/suggestions`. A cap, not
    an offset -- TDD §8.1/§9 forbid offset pagination anywhere."""

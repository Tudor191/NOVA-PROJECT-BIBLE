"""Kernel configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_OS_KERNEL_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"
    postgres_dsn: str = "postgresql+asyncpg://nova:nova@localhost:5432/nova"

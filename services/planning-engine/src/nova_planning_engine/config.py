"""Planning Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLANNING_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    decomposition_confidence_threshold: float = 0.6
    """Fork 3B-3 (docs/design/phase-3/05-tdd-3b-planning-engine.md §7):
    `reasoning.process.completed` below this `confidence_score` is not
    decomposed. Reuses `reasoning-engine`'s own `DEFAULT_VERIFY_THRESHOLD`
    value rather than inventing a second, arbitrary constant -- the TDD's
    own proposal, not silently assumed: flagged as an unconfirmed default
    in this unit's Gate Review, not yet given an explicit numeric approval
    by name."""

    decomposition_model_orchestration_timeout_ms: int = 10_000
    """Passed to `ModelOrchestrationClient` -- matches `reasoning-engine`'s
    own default for the same RPC (generation calls are slow)."""

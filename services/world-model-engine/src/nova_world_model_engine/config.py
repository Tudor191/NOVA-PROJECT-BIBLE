"""World Model Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORLD_MODEL_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `world_model` schema (ORM, Alembic) --
    `object_state_history`, `snapshot`, `prediction`, `conflict_log`,
    `outbox_event`. Neo4j connection details are not a `Settings` field:
    `nova_graphstore_sdk.factory.get_graph_store()` reads
    `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`/`GRAPH_STORE_BACKEND` directly,
    matching Knowledge Engine's own `config.py`. There is deliberately no
    `vector_store_dsn()` here -- §10: World Model Engine does not embed."""

    redis_url: str = "redis://localhost:6379/0"
    """Active Context and Attention's *primary* store (§4/§9), not a cache --
    Working Memory's own precedent in Memory Engine's `config.py`, applied
    here to the highest-QPS path in Phase 1 (`world_model.context.request`)."""

    attention_half_life_minutes: int = 30
    """docs/design/phase-1/03-world-model-engine.md §6's lazy-decay formula
    parameter -- see `domain/attention.py`'s `DEFAULT_HALF_LIFE` docstring for
    why this is a starting point, not a derived value."""

    idle_timeout_minutes: int = 15
    """How long an `ACTIVE` object should go without a related perception
    event before transitioning to `IDLE` (§6) -- consumed today only by
    `domain/state_management.next_state_on_idle_timeout`, which is unit-tested
    but has no scheduled caller yet (see README's Known Limitations: no
    idle-sweep worker exists in Phase 1). A per-object-type threshold is noted
    as the eventual design in §6; Phase 1 applies one engine-wide value."""

    snapshot_interval_hours: int = 6
    """docs/design/phase-1/03-world-model-engine.md §2: scheduled World State
    Snapshots, matching Memory Engine's `consolidation_interval_hours` and
    Knowledge Engine's `maintenance_interval_hours` accepted fixed-interval
    tradeoff for Phase 1."""

    graph_write_degraded_threshold_minutes: int = 15
    """Same operational signal as Knowledge Engine §02 §17 step 4, applied to
    World Model's identical Postgres-then-Neo4j saga (§17)."""

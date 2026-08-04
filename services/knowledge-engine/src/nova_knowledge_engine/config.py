"""Knowledge Engine configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_ENGINE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova"
    """SQLAlchemy-format DSN for the `knowledge` schema (ORM, Alembic). The
    `nova-vectorstore-sdk` pgvector backend needs the same database without the
    `+asyncpg` dialect qualifier -- see `vector_store_dsn()`, a derived value
    rather than a second setting that could drift from this one. Neo4j connection
    details are not a `Settings` field: `nova_graphstore_sdk.factory.get_graph_store()`
    reads `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`/`GRAPH_STORE_BACKEND` directly,
    matching how `get_event_bus()`/`get_embedding_provider()` already work."""

    redis_url: str = "redis://localhost:6379/0"

    embedding_model: str = "nomic-embed-text"  # ADR-010

    maintenance_interval_hours: int = 6
    """docs/design/phase-1/02-knowledge-engine.md §6: fixed interval for Phase 1,
    driving `workers/maintenance_worker.py` (evolution, discovery, compression)."""

    graph_write_degraded_threshold_minutes: int = 15
    """docs/design/phase-1/02-knowledge-engine.md §17 step 4: an outbox row still
    pending its Neo4j write past this age triggers the
    `knowledge_engine_graph_write_degraded` metric."""

    def vector_store_dsn(self) -> str:
        return self.postgres_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

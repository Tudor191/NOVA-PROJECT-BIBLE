"""nova-core configuration, twelve-factor style (docs/architecture/03-backend-architecture.md §6).

Only nova-core's own local knobs live here. `EVENT_BUS_BACKEND` / `NATS_URL` are read
directly by `nova_eventbus_sdk`, and `OTEL_EXPORTER_OTLP_ENDPOINT` directly by
`nova_observability` -- both are standard, unprefixed names shared by every engine, so
they are deliberately not duplicated under a `NOVA_CORE_` prefix here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class NovaCoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOVA_CORE_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"
    heartbeat_interval_s: float = 5.0

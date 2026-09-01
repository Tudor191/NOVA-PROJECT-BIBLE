"""Ws Gateway configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WS_GATEWAY_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    # --- session (decision D-3) -------------------------------------------
    # The same single local token `api-gateway` validates. Both gateways are
    # external surfaces of one instance, so they share one credential.
    # Empty means "not configured": every connection is then refused rather
    # than accepted, so a missing configuration fails closed.
    session_token: str = ""
    session_cookie_name: str = "nova_session"

    # Frames buffered per connection before a slow client is dropped. A
    # browser that cannot keep up must not be able to grow the bridge's
    # memory without bound.
    max_queued_frames: int = 256

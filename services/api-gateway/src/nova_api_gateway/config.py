"""Api Gateway configuration, twelve-factor style
(docs/architecture/03-backend-architecture.md §6)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="API_GATEWAY_", env_file=".env.local", extra="ignore"
    )

    http_port: int = 8000
    log_level: str = "INFO"

    # --- upstream engines -------------------------------------------------
    # One base URL per engine the gateway fronts. Paths are never rewritten
    # (decision D-6) -- the gateway forwards `/v1/...` verbatim.
    #
    # 4A wired communication-engine only. 4B adds the four the observability
    # panels read from; each already exposed the `/v1` surface being fronted,
    # so no engine API changed to make this possible.
    communication_engine_url: str = "http://communication-engine:8000"
    planning_engine_url: str = "http://planning-engine:8000"
    reasoning_engine_url: str = "http://reasoning-engine:8000"
    capability_engine_url: str = "http://capability-engine:8000"
    action_engine_url: str = "http://action-engine:8000"
    agent_os_kernel_url: str = "http://agent-os-kernel:8000"
    """Phase 4C (D-4). Matches the compose service name added by 4C.1;
    `agent-os/kernel` is control-plane infrastructure rather than an
    engine, but it is fronted on exactly the same terms as one."""

    autonomy_engine_url: str = "http://autonomy-engine:8000"
    """Phase 4D. The Autonomy panel's data source -- levels, policies,
    permissions and the AC-5 suggestion inbox. One prefix, `/v1/autonomy`,
    forwarded 1:1 (D-6)."""

    digital_twin_engine_url: str = "http://digital-twin-engine:8000"
    """Phase 4E. The Digital Twin panel's data source -- Bible Part 16's eleven
    domains and the AC-6 project reconstruction. One prefix,
    `/v1/digital-twin`, forwarded 1:1 (D-6)."""

    cognitive_state_engine_url: str = "http://cognitive-state-engine:8000"
    """Phase 4F.7 (RS-5). The Cognitive State panel's data source -- Active
    Thoughts, Focus and last-reported sensor state. One prefix,
    `/v1/cognitive-state`, forwarded 1:1 (D-6); the engine serves `GET` only."""

    upstream_timeout_seconds: float = 30.0

    # --- session (decision D-3) -------------------------------------------
    # A single long-lived local token, generated at first run, grounded in
    # ADR-025's single-trusted-user-per-instance assumption. Full OIDC via a
    # real `nova-auth` is Phase 7. Empty means "not configured": the gateway
    # then refuses every authenticated request rather than allowing all of
    # them, so a missing configuration fails closed.
    session_token: str = ""
    session_cookie_name: str = "nova_session"
    session_cookie_secure: bool = True
    session_cookie_max_age_seconds: int = 60 * 60 * 24 * 30

    # --- rate limiting ----------------------------------------------------
    # Redis-backed token bucket per (session, endpoint class), doc 11 §5.
    # Redis already exists in the local stack; no new infrastructure.
    redis_url: str = "redis://redis:6379/0"
    rate_limit_enabled: bool = True
    rate_limit_read_per_minute: int = 600
    rate_limit_write_per_minute: int = 120

"""nova_api_gateway's FastAPI entrypoint.

`api-gateway` is the one stable, versioned surface the outside world talks
to (doc 11 §1). It fronts each engine's already-built `/v1` REST surface,
forwarding **verbatim** (decision D-6), wraps every response in doc 11 §4's
envelope, and terminates the Phase-4-scoped session model (decision D-3).

It owns no domain data and publishes no events: `PUBLISHABLE_SUBJECTS` and
`SUBSCRIBABLE_SUBJECTS` are both empty by design. Reads reach the browser
through `ws-gateway`, which is the only component permitted to bridge bus
subjects to a client (doc 09 §6).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from nova_observability import configure_observability, get_logger, prometheus_asgi_app

from nova_api_gateway.api.auth import router as auth_router
from nova_api_gateway.api.forward import router as forward_router
from nova_api_gateway.api.health import router as health_router
from nova_api_gateway.clients.upstream import UpstreamClient
from nova_api_gateway.config import Settings
from nova_api_gateway.domain.rate_limit import InMemoryRateLimiter, NullRateLimiter
from nova_api_gateway.domain.routing import build_route_table
from nova_api_gateway.domain.session import LocalTokenSessionValidator

logger = get_logger("api-gateway")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_observability("api-gateway", log_level=settings.log_level)

    route_table = build_route_table(
        communication_engine_url=settings.communication_engine_url
    )
    session_validator = LocalTokenSessionValidator(settings.session_token)

    if not session_validator.configured:
        # Loud, because the gateway will refuse every request in this state.
        # Silence here would look like a broken frontend rather than an
        # unprovisioned instance.
        logger.warning(
            "no session token configured; every authenticated request will be "
            "refused. Set API_GATEWAY_SESSION_TOKEN to provision this instance."
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "api-gateway starting",
            extra={"routes": [r.prefix for r in route_table.routes]},
        )
        async with httpx.AsyncClient(
            timeout=settings.upstream_timeout_seconds, follow_redirects=False
        ) as client:
            app.state.upstream = UpstreamClient(client)
            app.state.ready = True
            yield
            logger.info("api-gateway shutting down")
            app.state.ready = False

    fastapi_app = FastAPI(title="api-gateway", version="0.1.0", lifespan=lifespan)

    fastapi_app.state.settings = settings
    fastapi_app.state.route_table = route_table
    fastapi_app.state.session_validator = session_validator
    fastapi_app.state.rate_limiter = (
        InMemoryRateLimiter(
            read_per_minute=settings.rate_limit_read_per_minute,
            write_per_minute=settings.rate_limit_write_per_minute,
        )
        if settings.rate_limit_enabled
        else NullRateLimiter()
    )

    fastapi_app.include_router(health_router)
    fastapi_app.include_router(auth_router)
    # Mounted last: its `/v1/{path:path}` catch-all must not shadow the
    # concrete `/v1/auth/session` routes declared above it.
    fastapi_app.include_router(forward_router)
    fastapi_app.mount("/internal/metrics", prometheus_asgi_app())
    return fastapi_app


app = create_app()

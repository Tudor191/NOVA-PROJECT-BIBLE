"""The forwarding surface.

Everything the outside world reaches goes through here. Three properties
this module is responsible for holding, all of them load-bearing:

1. **`/internal/*` is never routable** (doc 11 §3). The route table refuses
   any prefix outside `/v1/`, and this router is mounted only on `/v1`, so
   there is no path from a browser to an engine's internal RPC surface. It
   also refuses any path it could not forward unchanged (`is_canonical`), so
   no caller can leave a prefix with `..` once `httpx` builds the URL
   (closure matrix R-06).
2. **Every request is authenticated** (D-3) before any upstream call is
   made, so an unauthenticated caller cannot even probe which engines exist.
3. **A failure is always a structured error**, never an empty success.

Every decision on that path -- refused, not routed, rate limited, upstream
unreachable, upstream error, forwarded -- is counted in
`api_gateway_requests_total` and timed in
`api_gateway_request_duration_seconds` (`observability.py`), and every
refusal or failure is logged with the request's `correlation_id`, so a
request's path through the gateway can be reconstructed from its logs alone
(SAD 15 §9.1 items 9 and 10).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from nova_observability import get_logger

from nova_api_gateway.clients.upstream import UpstreamUnavailableError
from nova_api_gateway.domain.envelope import (
    CORRELATION_ID_HEADER,
    failure,
    new_correlation_id,
    success,
)
from nova_api_gateway.domain.routing import endpoint_class
from nova_api_gateway.domain.session import extract_presented_token

logger = get_logger("api-gateway")

router = APIRouter(tags=["forward"])

_FORWARDABLE_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def _correlation_id(request: Request) -> str:
    return request.headers.get(CORRELATION_ID_HEADER) or new_correlation_id()


def _record(request: Request, *, upstream: str, outcome: str, started: float) -> None:
    """Count and time one forwarding decision. A no-op if metrics are absent."""
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        return
    metrics.requests_total.add(
        1, {"upstream": upstream, "method": request.method.upper(), "outcome": outcome}
    )
    metrics.request_duration_seconds.record(
        time.perf_counter() - started, {"upstream": upstream, "outcome": outcome}
    )


def _refused(request: Request, *, reason: str, path: str, correlation_id: str) -> None:
    logger.info(
        "request refused",
        extra={
            "reason": reason,
            "method": request.method.upper(),
            "path": path,
            "correlation_id": correlation_id,
        },
    )


@router.api_route("/v1/{path:path}", methods=_FORWARDABLE_METHODS)
async def forward(path: str, request: Request) -> Response:
    started = time.perf_counter()
    correlation_id = _correlation_id(request)
    settings = request.app.state.settings
    validator = request.app.state.session_validator
    table = request.app.state.route_table
    client = request.app.state.upstream

    full_path = f"/v1/{path}"

    # --- authentication, before anything else ---------------------------
    presented = extract_presented_token(
        request.cookies.get(settings.session_cookie_name),
        request.headers.get("authorization"),
    )
    if not validator.is_valid(presented):
        _refused(request, reason="unauthenticated", path=full_path, correlation_id=correlation_id)
        _record(request, upstream="none", outcome="unauthenticated", started=started)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=failure(
                "unauthenticated",
                "A valid session is required.",
                correlation_id,
            ).model_dump(mode="json"),
            headers={CORRELATION_ID_HEADER: correlation_id},
        )

    # --- routing ---------------------------------------------------------
    route = table.resolve(full_path)
    if route is None:
        # Not an allow-listed prefix. 404 rather than proxying whatever the
        # caller named -- the table is an allow-list, not a pattern.
        _refused(request, reason="no_route", path=full_path, correlation_id=correlation_id)
        _record(request, upstream="none", outcome="no_route", started=started)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=failure(
                "no_route",
                f"No upstream is configured for {full_path!r}.",
                correlation_id,
            ).model_dump(mode="json"),
            headers={CORRELATION_ID_HEADER: correlation_id},
        )

    # --- rate limiting ---------------------------------------------------
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        allowed = await limiter.allow(
            session_key="local", endpoint_class=endpoint_class(request.method)
        )
        if not allowed:
            logger.warning(
                "request refused",
                extra={
                    "reason": "rate_limited",
                    "endpoint_class": endpoint_class(request.method),
                    "upstream": route.upstream_name,
                    "method": request.method.upper(),
                    "path": full_path,
                    "correlation_id": correlation_id,
                },
            )
            _record(request, upstream=route.upstream_name, outcome="rate_limited", started=started)
            # TDD 4A §7: "429 with a structured retry hint". The standard
            # header, so the envelope's error schema is unchanged.
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=failure(
                    "rate_limited",
                    "Too many requests for this endpoint class.",
                    correlation_id,
                ).model_dump(mode="json"),
                headers={
                    CORRELATION_ID_HEADER: correlation_id,
                    "Retry-After": str(limiter.retry_after_seconds()),
                },
            )

    # --- forward, 1:1, no path rewriting (D-6) ---------------------------
    body = await request.body()
    headers = dict(request.headers)
    headers[CORRELATION_ID_HEADER] = correlation_id

    upstream_started = time.perf_counter()
    try:
        upstream = await client.forward(
            method=request.method,
            url=f"{route.base_url}{full_path}",
            headers=headers,
            params=list(request.query_params.multi_items()),
            content=body or None,
        )
    except UpstreamUnavailableError as exc:
        _record_upstream(request, route.upstream_name, "upstream_unavailable", upstream_started)
        logger.warning(
            "upstream unavailable",
            extra={
                "upstream": route.upstream_name,
                "method": request.method.upper(),
                "path": full_path,
                "correlation_id": correlation_id,
            },
        )
        _record(
            request, upstream=route.upstream_name, outcome="upstream_unavailable", started=started
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=failure(
                "upstream_unavailable", str(exc), correlation_id
            ).model_dump(mode="json"),
            headers={CORRELATION_ID_HEADER: correlation_id},
        )

    if upstream.status_code >= 400:
        _record_upstream(request, route.upstream_name, "upstream_error", upstream_started)
        logger.info(
            "upstream returned an error",
            extra={
                "upstream": route.upstream_name,
                "upstream_status": upstream.status_code,
                "method": request.method.upper(),
                "path": full_path,
                "correlation_id": correlation_id,
            },
        )
        _record(request, upstream=route.upstream_name, outcome="upstream_error", started=started)
        return JSONResponse(
            status_code=upstream.status_code,
            content=failure(
                "upstream_error",
                _upstream_message(upstream.json_body, upstream.text_body),
                correlation_id,
                upstream_status=upstream.status_code,
            ).model_dump(mode="json"),
            headers={CORRELATION_ID_HEADER: correlation_id},
        )

    _record_upstream(request, route.upstream_name, "forwarded", upstream_started)
    _record(request, upstream=route.upstream_name, outcome="forwarded", started=started)
    return JSONResponse(
        status_code=upstream.status_code,
        content=success(upstream.json_body, correlation_id).model_dump(mode="json"),
        headers={CORRELATION_ID_HEADER: correlation_id},
    )


def _record_upstream(request: Request, upstream: str, outcome: str, started: float) -> None:
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        return
    metrics.upstream_duration_seconds.record(
        time.perf_counter() - started, {"upstream": upstream, "outcome": outcome}
    )


def _upstream_message(json_body: object | None, text_body: str) -> str:
    """Surface the engine's own message rather than a generic one."""
    if isinstance(json_body, dict):
        detail = json_body.get("detail")
        if isinstance(detail, str) and detail:
            return detail
        message = json_body.get("message")
        if isinstance(message, str) and message:
            return message
    return text_body[:500] or "The upstream engine returned an error."

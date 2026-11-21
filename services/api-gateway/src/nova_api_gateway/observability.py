"""Observability instruments for `api-gateway` (SAD 15 §9.1 item 10).

`create_metrics()` follows every other engine's `observability.py`
convention: it must only be called after `configure_observability()` has
run, and `domain/` never imports this module -- the API layer reads the
instruments off `app.state.metrics`.

**Every label is bounded.** `upstream` is a route-table name or `"none"`,
`method` is one of the five forwardable verbs, and `outcome` is one of
`REQUEST_OUTCOMES` / `SESSION_OUTCOMES`. No path, query string, token or
correlation id is ever a label: paths carry identifiers, and an unbounded
label set is a memory leak in the scrape target.

**Latency buckets are in seconds.** The OpenTelemetry SDK's default
histogram boundaries (0, 5, 10, ... 10000) assume milliseconds; recorded in
seconds, every sub-five-second request would land in one bucket and no
quantile could be computed. Each histogram therefore carries its own
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass

from nova_observability import get_meter
from opentelemetry.metrics import Counter, Histogram

__all__ = [
    "LATENCY_BUCKETS_SECONDS",
    "REQUEST_OUTCOMES",
    "SESSION_OUTCOMES",
    "GatewayMetrics",
    "create_metrics",
]

#: Every value `api_gateway_requests_total`'s `outcome` label can take.
REQUEST_OUTCOMES: frozenset[str] = frozenset(
    {
        "forwarded",  # the upstream answered < 400
        "upstream_error",  # the upstream answered >= 400; mapped, not hidden
        "upstream_unavailable",  # the upstream could not be reached -> 502
        "unauthenticated",  # refused before any upstream call -> 401
        "no_route",  # not an allow-listed prefix -> 404
        "rate_limited",  # refused by the limiter -> 429
    }
)

#: Every value `api_gateway_session_exchanges_total`'s `outcome` can take.
SESSION_OUTCOMES: frozenset[str] = frozenset({"issued", "invalid_token", "not_configured"})

#: Upper bounds, in seconds. Dense below one second, where a gateway's own
#: overhead and a healthy upstream live; coarse above it, up to the
#: configured upstream timeout's order of magnitude.
LATENCY_BUCKETS_SECONDS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
)


@dataclass(frozen=True)
class GatewayMetrics:
    requests_total: Counter
    """Every `/v1/*` forwarding decision, labeled by `upstream`, `method`
    and `outcome` -- the gateway's rate and failure rate."""

    request_duration_seconds: Histogram
    """Wall-clock time from receiving a `/v1/*` request to answering it,
    labeled by `upstream` and `outcome`."""

    upstream_duration_seconds: Histogram
    """Time spent inside the upstream call alone, labeled by `upstream` and
    `outcome` (`forwarded`, `upstream_error` or `upstream_unavailable`).
    The difference from `request_duration_seconds` is the gateway's own
    overhead."""

    session_exchanges_total: Counter
    """`POST /v1/auth/session` results, labeled by `outcome`. A rising
    `invalid_token` rate is the signal of a guessing caller."""


def create_metrics() -> GatewayMetrics:
    meter = get_meter("api-gateway")
    return GatewayMetrics(
        requests_total=meter.create_counter(
            "api_gateway_requests_total",
            description="Forwarding decisions, labeled by upstream, method and outcome.",
        ),
        request_duration_seconds=meter.create_histogram(
            "api_gateway_request_duration_seconds",
            unit="s",
            description="Time to answer a /v1 request, labeled by upstream and outcome.",
            explicit_bucket_boundaries_advisory=LATENCY_BUCKETS_SECONDS,
        ),
        upstream_duration_seconds=meter.create_histogram(
            "api_gateway_upstream_duration_seconds",
            unit="s",
            description="Time spent in the upstream call, labeled by upstream and outcome.",
            explicit_bucket_boundaries_advisory=LATENCY_BUCKETS_SECONDS,
        ),
        session_exchanges_total=meter.create_counter(
            "api_gateway_session_exchanges_total",
            description="Session token exchanges, labeled by outcome.",
        ),
    )

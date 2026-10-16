"""SAD 15 §9.1 items 9 and 10 for `api-gateway`, asserted through a real
`create_app()`.

Each forwarding decision must be **counted** in `api_gateway_requests_total`
under exactly one bounded `outcome`, **timed**, and -- for every refusal or
failure -- **logged with the request's own `correlation_id`**, so a request
can be followed through the gateway from its logs alone. The session token
must never appear in a log line or a metric label.

Metrics are read the way Prometheus reads them: by scraping
`/internal/metrics`. The meter provider is process-global, so every
assertion is a delta around the request under test, never an absolute.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from nova_api_gateway.clients.upstream import UpstreamResponse, UpstreamUnavailableError
from nova_api_gateway.config import Settings
from nova_api_gateway.main import create_app
from nova_api_gateway.observability import LATENCY_BUCKETS_SECONDS, REQUEST_OUTCOMES

TOKEN = "observability-test-token"
UPSTREAM = "communication-engine"


@dataclass
class FakeUpstream:
    status_code: int = 200
    json_body: Any = field(default_factory=lambda: {"ok": True})
    raise_unavailable: bool = False

    async def forward(self, **_: Any) -> UpstreamResponse:
        if self.raise_unavailable:
            raise UpstreamUnavailableError("upstream unreachable")
        return UpstreamResponse(
            status_code=self.status_code, json_body=self.json_body, text_body="", headers={}
        )


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def records() -> Iterator[list[logging.LogRecord]]:
    """Attached to the `api-gateway` logger itself, not the root logger:
    `configure_logging` replaces the root handlers on first use, which would
    silently detach pytest's `caplog`."""
    handler = _Records()
    gateway_logger = logging.getLogger("api-gateway")
    gateway_logger.addHandler(handler)
    previous = gateway_logger.level
    gateway_logger.setLevel(logging.DEBUG)
    try:
        yield handler.records
    finally:
        gateway_logger.removeHandler(handler)
        gateway_logger.setLevel(previous)


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "session_token": TOKEN,
        "communication_engine_url": "http://communication-engine:8000",
        "session_cookie_secure": False,
        "rate_limit_enabled": False,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def upstream() -> FakeUpstream:
    return FakeUpstream()


@pytest.fixture
def client(upstream: FakeUpstream) -> Iterator[TestClient]:
    app = create_app(_settings())
    with TestClient(app) as test_client:
        app.state.upstream = upstream
        yield test_client


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


_SAMPLE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)\{(?P<labels>[^}]*)\} (?P<value>\S+)$")


def _sample(scrape: str, name: str, **labels: str) -> float:
    """Sum of every sample of `name` whose labels include `labels`."""
    total = 0.0
    for line in scrape.splitlines():
        match = _SAMPLE.match(line)
        if match is None or match["name"] != name:
            continue
        found = dict(re.findall(r'(\w+)="([^"]*)"', match["labels"]))
        if all(found.get(key) == value for key, value in labels.items()):
            total += float(match["value"])
    return total


def _scrape(client: TestClient) -> str:
    response = client.get("/internal/metrics")
    assert response.status_code == 200
    return response.text


def _refusal(
    records: list[logging.LogRecord], reason: str
) -> logging.LogRecord:
    matching = [
        r
        for r in records
        if r.getMessage() == "request refused" and getattr(r, "reason", None) == reason
    ]
    assert len(matching) == 1, f"expected one {reason!r} refusal log, got {len(matching)}"
    return matching[0]


# --- the four refusal / failure decisions ----------------------------------


def test_an_unauthenticated_request_is_counted_and_logged_with_its_correlation_id(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    labels = {"upstream": "none", "method": "GET", "outcome": "unauthenticated"}
    before = _sample(_scrape(client), "api_gateway_requests_total", **labels)

    response = client.get("/v1/communication/sessions")

    assert response.status_code == 401
    after = _sample(_scrape(client), "api_gateway_requests_total", **labels)
    assert after - before == 1
    record = _refusal(records, "unauthenticated")
    assert record.correlation_id == response.headers["X-Correlation-ID"]  # type: ignore[attr-defined]
    assert record.path == "/v1/communication/sessions"  # type: ignore[attr-defined]


def test_a_request_with_no_route_is_counted_and_logged(
    client: TestClient, records: list[logging.LogRecord]
) -> None:
    labels = {"upstream": "none", "outcome": "no_route"}
    before = _sample(_scrape(client), "api_gateway_requests_total", **labels)

    response = client.get("/v1/no-such-engine/things", headers=_auth_header())

    assert response.status_code == 404
    assert _sample(_scrape(client), "api_gateway_requests_total", **labels) - before == 1
    record = _refusal(records, "no_route")
    assert record.correlation_id == response.headers["X-Correlation-ID"]  # type: ignore[attr-defined]


def test_a_rate_limited_request_is_counted_and_logged_at_warning(
    upstream: FakeUpstream, records: list[logging.LogRecord]
) -> None:
    app = create_app(_settings(rate_limit_enabled=True, rate_limit_read_per_minute=1))
    labels = {"upstream": UPSTREAM, "outcome": "rate_limited"}
    with TestClient(app) as limited:
        app.state.upstream = upstream
        before = _sample(_scrape(limited), "api_gateway_requests_total", **labels)
        assert limited.get("/v1/communication/sessions", headers=_auth_header()).status_code == 200
        response = limited.get("/v1/communication/sessions", headers=_auth_header())

        assert response.status_code == 429
        assert _sample(_scrape(limited), "api_gateway_requests_total", **labels) - before == 1
    record = _refusal(records, "rate_limited")
    assert record.levelno == logging.WARNING
    assert record.endpoint_class == "read"  # type: ignore[attr-defined]
    assert record.correlation_id == response.headers["X-Correlation-ID"]  # type: ignore[attr-defined]


def test_an_unreachable_upstream_is_counted_timed_and_logged(
    client: TestClient, upstream: FakeUpstream, records: list[logging.LogRecord]
) -> None:
    upstream.raise_unavailable = True
    labels = {"upstream": UPSTREAM, "outcome": "upstream_unavailable"}
    scrape = _scrape(client)
    before_total = _sample(scrape, "api_gateway_requests_total", **labels)
    before_timed = _sample(scrape, "api_gateway_upstream_duration_seconds_count", **labels)

    response = client.get("/v1/communication/sessions", headers=_auth_header())

    assert response.status_code == 502
    scrape = _scrape(client)
    assert _sample(scrape, "api_gateway_requests_total", **labels) - before_total == 1
    timed = _sample(scrape, "api_gateway_upstream_duration_seconds_count", **labels)
    assert timed - before_timed == 1
    [record] = [r for r in records if r.getMessage() == "upstream unavailable"]
    assert record.correlation_id == response.headers["X-Correlation-ID"]  # type: ignore[attr-defined]
    assert record.upstream == UPSTREAM  # type: ignore[attr-defined]


def test_an_upstream_error_is_counted_and_logged_with_the_upstream_status(
    client: TestClient, upstream: FakeUpstream, records: list[logging.LogRecord]
) -> None:
    upstream.status_code = 503
    upstream.json_body = {"detail": "registry unavailable"}
    labels = {"upstream": UPSTREAM, "outcome": "upstream_error"}
    before = _sample(_scrape(client), "api_gateway_requests_total", **labels)

    response = client.get("/v1/communication/sessions", headers=_auth_header())

    assert response.status_code == 503
    assert _sample(_scrape(client), "api_gateway_requests_total", **labels) - before == 1
    [record] = [r for r in records if r.getMessage() == "upstream returned an error"]
    assert record.upstream_status == 503  # type: ignore[attr-defined]
    assert record.correlation_id == response.headers["X-Correlation-ID"]  # type: ignore[attr-defined]


# --- the success path ------------------------------------------------------


def test_a_forwarded_request_is_counted_and_timed_end_to_end_and_upstream(
    client: TestClient,
) -> None:
    labels = {"upstream": UPSTREAM, "outcome": "forwarded"}
    scrape = _scrape(client)
    before = {
        name: _sample(scrape, name, **labels)
        for name in (
            "api_gateway_requests_total",
            "api_gateway_request_duration_seconds_count",
            "api_gateway_upstream_duration_seconds_count",
        )
    }

    assert client.post(
        "/v1/communication/sessions", json={"x": 1}, headers=_auth_header()
    ).status_code == 200

    scrape = _scrape(client)
    for name, value in before.items():
        assert _sample(scrape, name, **labels) - value == 1, name
    assert (
        _sample(_scrape(client), "api_gateway_requests_total", method="POST", **labels) >= 1
    )


def test_latency_is_bucketed_in_seconds_not_the_sdk_millisecond_default(
    client: TestClient,
) -> None:
    client.get("/v1/communication/sessions", headers=_auth_header())
    scrape = _scrape(client)
    bounds = {
        float(le)
        for le in re.findall(
            r'^api_gateway_request_duration_seconds_bucket\{[^}]*le="([^"+]+)"',
            scrape,
            flags=re.MULTILINE,
        )
    }
    assert bounds == set(LATENCY_BUCKETS_SECONDS)
    assert 0.005 in bounds  # five milliseconds is resolvable


# --- session exchange ------------------------------------------------------


def test_session_exchange_outcomes_are_counted_and_the_token_is_never_logged(
    client: TestClient, upstream: FakeUpstream, records: list[logging.LogRecord]
) -> None:
    def exchanges(scrape: str, outcome: str) -> float:
        return _sample(scrape, "api_gateway_session_exchanges_total", outcome=outcome)

    near_miss = TOKEN + "-guess"
    scrape = _scrape(client)
    before = {o: exchanges(scrape, o) for o in ("issued", "invalid_token", "not_configured")}

    assert client.post("/v1/auth/session", json={"token": TOKEN}).status_code == 200
    assert client.post("/v1/auth/session", json={"token": near_miss}).status_code == 401
    unconfigured = create_app(_settings(session_token=""))
    with TestClient(unconfigured) as other:
        other.app.state.upstream = upstream  # type: ignore[attr-defined]
        assert other.post("/v1/auth/session", json={"token": "x"}).status_code == 503

    scrape = _scrape(client)
    assert exchanges(scrape, "issued") - before["issued"] == 1
    assert exchanges(scrape, "invalid_token") - before["invalid_token"] == 1
    assert exchanges(scrape, "not_configured") - before["not_configured"] == 1

    rendered = " ".join(
        f"{r.getMessage()} {sorted(vars(r).items())}" for r in records
    )
    assert TOKEN not in rendered
    assert near_miss not in rendered
    assert TOKEN not in scrape


# --- label hygiene -----------------------------------------------------------


def test_no_gateway_metric_label_carries_a_path_or_an_unbounded_outcome(
    client: TestClient, upstream: FakeUpstream
) -> None:
    client.get("/v1/communication/sessions/123e4567-e89b-12d3-a456-426614174000")
    client.get("/v1/communication/sessions", headers=_auth_header())
    client.get("/v1/unknown/x", headers=_auth_header())
    upstream.status_code = 404
    client.get("/v1/communication/sessions/missing", headers=_auth_header())

    gateway_lines = [
        line
        for line in _scrape(client).splitlines()
        if line.startswith("api_gateway_requests_total{")
    ]
    assert gateway_lines
    for line in gateway_lines:
        assert "/v1/" not in line
        assert "123e4567" not in line
        outcome = re.search(r'outcome="([^"]*)"', line)
        assert outcome is not None and outcome.group(1) in REQUEST_OUTCOMES

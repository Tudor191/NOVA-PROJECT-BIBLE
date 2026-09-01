"""Unit tests for the gateway's domain layer: envelope, session, routing, limits."""

from __future__ import annotations

import pytest
from nova_api_gateway.domain.envelope import failure, new_correlation_id, success
from nova_api_gateway.domain.rate_limit import InMemoryRateLimiter, NullRateLimiter
from nova_api_gateway.domain.routing import (
    RouteTable,
    UpstreamRoute,
    build_route_table,
    endpoint_class,
)
from nova_api_gateway.domain.session import (
    LocalTokenSessionValidator,
    extract_presented_token,
)

# --- envelope, doc 11 §4 -------------------------------------------------


def test_success_envelope_shape() -> None:
    env = success({"id": "abc"}, "corr-1")
    assert env.data == {"id": "abc"}
    assert env.meta.correlation_id == "corr-1"
    assert env.meta.generated_at is not None
    assert env.error is None


def test_failure_envelope_never_carries_data() -> None:
    """A degraded upstream must never look like an empty success."""
    env = failure("upstream_unavailable", "boom", "corr-2", upstream_status=502)
    assert env.data is None
    assert env.error is not None
    assert env.error.code == "upstream_unavailable"
    assert env.error.upstream_status == 502


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"confidence": 0.87}, 0.87),
        ({"confidence": 0}, 0.0),
        ({"confidence": 1}, 1.0),
        ({"confidence": 1.5}, None),  # out of range
        ({"confidence": -0.1}, None),  # out of range
        ({"confidence": "high"}, None),  # not numeric
        ({"confidence": True}, None),  # bool is not a confidence
        ({"other": 1}, None),  # absent
        ([1, 2, 3], None),  # not an object
        (None, None),
    ],
)
def test_confidence_is_passed_through_never_invented(
    payload: object, expected: float | None
) -> None:
    """Doc 11 §4 surfaces confidence as Part 8's signal; guessing corrupts it."""
    assert success(payload, "c").meta.confidence == expected


def test_correlation_ids_are_unique() -> None:
    assert new_correlation_id() != new_correlation_id()


# --- session, decision D-3 ------------------------------------------------


def test_unconfigured_validator_fails_closed() -> None:
    """No credential provisioned must refuse everything, not allow everything."""
    validator = LocalTokenSessionValidator("")
    assert validator.configured is False
    assert validator.is_valid("anything") is False
    assert validator.is_valid("") is False
    assert validator.is_valid(None) is False


def test_configured_validator_accepts_only_the_token() -> None:
    validator = LocalTokenSessionValidator("s3cret")
    assert validator.configured is True
    assert validator.is_valid("s3cret") is True
    assert validator.is_valid("s3cre") is False
    assert validator.is_valid("s3crett") is False
    assert validator.is_valid(None) is False


@pytest.mark.parametrize(
    ("cookie", "header", "expected"),
    [
        ("tok", None, "tok"),
        (None, "Bearer tok", "tok"),
        (None, "bearer tok", "tok"),
        ("cookie-tok", "Bearer header-tok", "cookie-tok"),  # cookie wins
        (None, "Basic tok", None),  # wrong scheme
        (None, "Bearer", None),  # no credential
        (None, None, None),
    ],
)
def test_token_extraction(
    cookie: str | None, header: str | None, expected: str | None
) -> None:
    assert extract_presented_token(cookie, header) == expected


# --- routing, decision D-6 ------------------------------------------------


def test_route_table_rejects_non_v1_prefixes() -> None:
    """`/internal/*` must be unroutable by construction, not by convention."""
    with pytest.raises(ValueError, match="must start with '/v1/'"):
        RouteTable([UpstreamRoute("/internal/health", "x", "http://x")])


def test_route_table_resolves_prefix_and_subpaths() -> None:
    table = build_route_table(communication_engine_url="http://comms:8000")
    assert table.resolve("/v1/communication") is not None
    assert table.resolve("/v1/communication/sessions") is not None
    assert table.resolve("/v1/communication/sessions/abc/messages") is not None


def test_route_table_is_an_allow_list_not_a_pattern() -> None:
    table = build_route_table(communication_engine_url="http://comms:8000")
    assert table.resolve("/v1/planning/plans") is None
    assert table.resolve("/v1/memories") is None
    assert table.resolve("/v1/communicationXX") is None  # no partial-name match


def test_longest_prefix_wins_regardless_of_order() -> None:
    table = RouteTable(
        [
            UpstreamRoute("/v1/a", "general", "http://general"),
            UpstreamRoute("/v1/a/specific", "specific", "http://specific"),
        ]
    )
    resolved = table.resolve("/v1/a/specific/thing")
    assert resolved is not None
    assert resolved.upstream_name == "specific"


def test_base_url_trailing_slash_is_normalised() -> None:
    table = build_route_table(communication_engine_url="http://comms:8000/")
    route = table.resolve("/v1/communication")
    assert route is not None
    assert route.base_url == "http://comms:8000"


@pytest.mark.parametrize(
    ("method", "expected"),
    [("GET", "read"), ("HEAD", "read"), ("POST", "write"), ("DELETE", "write")],
)
def test_endpoint_class(method: str, expected: str) -> None:
    assert endpoint_class(method) == expected


# --- rate limiting, doc 11 §5 --------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_limiter_blocks_past_the_limit() -> None:
    limiter = InMemoryRateLimiter(read_per_minute=2, write_per_minute=1)
    assert await limiter.allow(session_key="s", endpoint_class="read") is True
    assert await limiter.allow(session_key="s", endpoint_class="read") is True
    assert await limiter.allow(session_key="s", endpoint_class="read") is False
    # A different class has its own budget.
    assert await limiter.allow(session_key="s", endpoint_class="write") is True
    assert await limiter.allow(session_key="s", endpoint_class="write") is False


@pytest.mark.asyncio
async def test_null_limiter_always_allows() -> None:
    limiter = NullRateLimiter()
    for _ in range(50):
        assert await limiter.allow(session_key="s", endpoint_class="write") is True

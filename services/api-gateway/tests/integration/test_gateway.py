"""Integration tests through a real `create_app()`.

The upstream engine is replaced with a recording fake so these run without
`communication-engine`; every other layer -- routing, auth, envelope,
error mapping, rate limiting -- is the real one.

The security assertions here are the ones Phase 4 **AC-2** turns on:
`/internal/*` must not be routable through the gateway, and an
unauthenticated caller must not be able to reach or probe an upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from nova_api_gateway.clients.upstream import (
    UpstreamResponse,
    UpstreamUnavailableError,
    filter_request_headers,
)
from nova_api_gateway.config import Settings
from nova_api_gateway.main import create_app

TOKEN = "test-session-token"


@dataclass
class FakeUpstream:
    """Records what the gateway forwarded, and returns what it is told to."""

    status_code: int = 200
    json_body: Any = field(default_factory=lambda: {"ok": True})
    raise_unavailable: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def forward(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: list[tuple[str, str]] | None = None,
        content: bytes | None = None,
    ) -> UpstreamResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "content": content,
            }
        )
        if self.raise_unavailable:
            raise UpstreamUnavailableError("upstream unreachable: " + url)
        return UpstreamResponse(
            status_code=self.status_code,
            json_body=self.json_body,
            text_body="",
            headers={},
        )


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
def client(upstream: FakeUpstream):  # type: ignore[no-untyped-def]
    app = create_app(_settings())
    with TestClient(app) as test_client:
        app.state.upstream = upstream  # after lifespan, which installs the real one
        yield test_client


def _auth(client: TestClient) -> None:
    response = client.post("/v1/auth/session", json={"token": TOKEN})
    assert response.status_code == 200


# --- health ---------------------------------------------------------------


def test_health_needs_no_session(client: TestClient) -> None:
    assert client.get("/internal/health").status_code == 200


# --- session, decision D-3 ------------------------------------------------


def test_session_exchange_sets_httponly_cookie(client: TestClient) -> None:
    response = client.post("/v1/auth/session", json={"token": TOKEN})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["authenticated"] is True
    assert body["error"] is None
    cookie_header = response.headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "SameSite=strict" in cookie_header


def test_session_exchange_rejects_a_wrong_token(client: TestClient) -> None:
    response = client.post("/v1/auth/session", json={"token": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_unconfigured_instance_reports_itself_rather_than_rejecting(
    upstream: FakeUpstream,
) -> None:
    """An unprovisioned gateway must be distinguishable from a bad password."""
    app = create_app(_settings(session_token=""))
    with TestClient(app) as unconfigured:
        app.state.upstream = upstream
        response = unconfigured.post("/v1/auth/session", json={"token": "anything"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "session_not_configured"


def test_session_state_round_trip(client: TestClient) -> None:
    assert client.get("/v1/auth/session").json()["data"]["authenticated"] is False
    _auth(client)
    assert client.get("/v1/auth/session").json()["data"]["authenticated"] is True
    client.delete("/v1/auth/session")
    assert client.get("/v1/auth/session").json()["data"]["authenticated"] is False


def test_bearer_token_is_accepted_for_non_browser_callers(
    client: TestClient, upstream: FakeUpstream
) -> None:
    response = client.get(
        "/v1/communication/sessions", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 200
    assert len(upstream.calls) == 1


# --- authentication gates forwarding -------------------------------------


def test_unauthenticated_request_is_refused_before_any_upstream_call(
    client: TestClient, upstream: FakeUpstream
) -> None:
    response = client.get("/v1/communication/sessions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    # The upstream must not have been probed at all.
    assert upstream.calls == []


def test_unauthenticated_unknown_route_does_not_leak_route_existence(
    client: TestClient,
) -> None:
    """401 before 404: an anonymous caller cannot enumerate fronted engines."""
    response = client.get("/v1/planning/plans")
    assert response.status_code == 401


# --- forwarding, decision D-6 --------------------------------------------


def test_path_is_forwarded_verbatim(client: TestClient, upstream: FakeUpstream) -> None:
    _auth(client)
    client.get("/v1/communication/sessions/abc/messages")
    call = upstream.calls[-1]
    assert call["url"] == "http://communication-engine:8000/v1/communication/sessions/abc/messages"


def test_query_parameters_are_preserved(
    client: TestClient, upstream: FakeUpstream
) -> None:
    _auth(client)
    client.get("/v1/communication/sessions?limit=10&cursor=x")
    assert ("limit", "10") in upstream.calls[-1]["params"]
    assert ("cursor", "x") in upstream.calls[-1]["params"]


def test_request_body_and_method_are_preserved(
    client: TestClient, upstream: FakeUpstream
) -> None:
    _auth(client)
    client.post("/v1/communication/sessions", json={"user_id": "u1"})
    call = upstream.calls[-1]
    assert call["method"] == "POST"
    assert b"u1" in call["content"]


def test_session_cookie_is_never_forwarded_upstream(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """The credential must not cross the trust boundary into an engine."""
    _auth(client)
    client.get("/v1/communication/sessions")
    forwarded = filter_request_headers(upstream.calls[-1]["headers"])
    assert "cookie" not in {k.lower() for k in forwarded}
    assert "authorization" not in {k.lower() for k in forwarded}


def test_correlation_id_is_propagated_and_echoed(
    client: TestClient, upstream: FakeUpstream
) -> None:
    _auth(client)
    response = client.get(
        "/v1/communication/sessions", headers={"x-correlation-id": "given-id"}
    )
    assert response.json()["meta"]["correlation_id"] == "given-id"
    assert response.headers["x-correlation-id"] == "given-id"
    assert upstream.calls[-1]["headers"]["x-correlation-id"] == "given-id"


def test_correlation_id_is_generated_when_absent(client: TestClient) -> None:
    _auth(client)
    response = client.get("/v1/communication/sessions")
    assert response.json()["meta"]["correlation_id"]


def test_response_is_wrapped_in_the_envelope(
    client: TestClient, upstream: FakeUpstream
) -> None:
    upstream.json_body = {"session_id": "s1", "confidence": 0.5}
    _auth(client)
    body = client.get("/v1/communication/sessions").json()
    assert body["data"] == {"session_id": "s1", "confidence": 0.5}
    assert body["meta"]["confidence"] == 0.5
    assert body["meta"]["generated_at"]
    assert body["error"] is None


def test_upstream_status_code_is_preserved(
    client: TestClient, upstream: FakeUpstream
) -> None:
    upstream.status_code = 201
    _auth(client)
    assert client.post("/v1/communication/sessions", json={}).status_code == 201


# --- security boundaries, Phase 4 AC-2 -----------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/internal/health",
        "/internal/readiness",
        "/v1/../internal/health",
    ],
)
def test_internal_surface_is_not_reachable_as_a_forwarded_route(
    path: str, client: TestClient, upstream: FakeUpstream
) -> None:
    """Doc 11 §3: no network path from a client to an engine's internal RPC."""
    _auth(client)
    client.get(path)
    forwarded_urls = [call["url"] for call in upstream.calls]
    assert not any("/internal/" in url for url in forwarded_urls)


def test_no_route_is_a_structured_404(client: TestClient, upstream: FakeUpstream) -> None:
    _auth(client)
    response = client.get("/v1/not-a-real-engine/thing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_route"
    assert upstream.calls == []


# --- degraded behaviour ---------------------------------------------------


def test_unreachable_upstream_is_a_structured_502_never_empty_success(
    client: TestClient, upstream: FakeUpstream
) -> None:
    upstream.raise_unavailable = True
    _auth(client)
    response = client.get("/v1/communication/sessions")
    assert response.status_code == 502
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "upstream_unavailable"


def test_upstream_error_surfaces_the_engines_own_message(
    client: TestClient, upstream: FakeUpstream
) -> None:
    upstream.status_code = 422
    upstream.json_body = {"detail": "session_id is not a valid UUID"}
    _auth(client)
    response = client.get("/v1/communication/sessions/xyz")
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "session_id is not a valid UUID"
    assert response.json()["error"]["upstream_status"] == 422


def test_rate_limit_returns_structured_429(upstream: FakeUpstream) -> None:
    app = create_app(
        _settings(rate_limit_enabled=True, rate_limit_read_per_minute=1)
    )
    with TestClient(app) as limited:
        app.state.upstream = upstream
        limited.post("/v1/auth/session", json={"token": TOKEN})
        assert limited.get("/v1/communication/sessions").status_code == 200
        response = limited.get("/v1/communication/sessions")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"


# --- Agents surface, Phase 4C milestone 4C.2c (decision D-4) ----------------
#
# The gateway's job here is exactly what it is for every other prefix: forward
# 1:1 to one upstream, apply doc 11 §4's envelope, and map an upstream failure
# to a structured error. These assert that the new prefix gets that same
# treatment and no special-casing -- the Kernel is the first non-`services/*`
# upstream, and that must change nothing about the mechanism.


@pytest.mark.parametrize(
    "path",
    [
        "/v1/agents",
        "/v1/agents/38a83c86-0000-0000-0000-000000000000",
        "/v1/agents/38a83c86-0000-0000-0000-000000000000/activity",
    ],
    ids=["list", "by-id", "activity"],
)
def test_agents_paths_forward_to_the_kernel_unrewritten(
    client: TestClient, upstream: FakeUpstream, path: str
) -> None:
    """D-6: paths are forwarded verbatim. The whole `/v1/agents` subtree
    resolves on one prefix, so `{id}` and `/activity` need no entries of their
    own."""
    _auth(client)
    response = client.get(path)

    assert response.status_code == 200
    assert upstream.calls[-1]["url"] == f"http://agent-os-kernel:8000{path}"


def test_agents_query_parameters_are_forwarded(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """Pagination is the Kernel's; the gateway must pass `limit`/`cursor`
    through untouched rather than interpreting them."""
    _auth(client)
    client.get(
        "/v1/agents/38a83c86-0000-0000-0000-000000000000/activity?limit=2&cursor=abc"
    )

    assert upstream.calls[-1]["params"] == [("limit", "2"), ("cursor", "abc")]


def test_agents_response_is_wrapped_in_the_standard_envelope(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """Envelope ownership: the Kernel returns bare models, the gateway wraps.
    If the Kernel ever emitted its own envelope this would show a doubly
    wrapped payload."""
    upstream.json_body = {"packages": [], "instances": [], "supervisors": []}
    _auth(client)
    response = client.get("/v1/agents")

    body = response.json()
    assert body["data"] == {"packages": [], "instances": [], "supervisors": []}
    assert body["error"] is None
    assert set(body["meta"]) == {"correlation_id", "generated_at", "confidence"}


def test_a_healthy_empty_agents_response_is_not_an_error(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """Decision D-1 through the gateway: an empty package list is a 200 whose
    `error` is null -- distinguishable from the 503 below."""
    upstream.json_body = {"packages": [], "instances": [], "supervisors": []}
    _auth(client)
    response = client.get("/v1/agents")

    assert response.status_code == 200
    assert response.json()["error"] is None
    assert response.json()["data"]["packages"] == []


def test_kernel_503_propagates_as_a_structured_failure(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """Decision D-1's other half. The Kernel answers 503 when Registry is
    unreachable; the gateway must carry the status through and populate
    `error`, never present it as an empty success."""
    upstream.status_code = 503
    upstream.json_body = {"detail": "The Agent Registry could not be reached."}
    _auth(client)
    response = client.get("/v1/agents")

    assert response.status_code == 503
    body = response.json()
    assert body["data"] is None
    assert body["error"]["upstream_status"] == 503
    assert body["error"]["message"] == "The Agent Registry could not be reached."


def test_kernel_404_propagates_for_an_unknown_instance(
    client: TestClient, upstream: FakeUpstream
) -> None:
    upstream.status_code = 404
    upstream.json_body = {"detail": "No agent instance found with id ..."}
    _auth(client)
    response = client.get("/v1/agents/38a83c86-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["data"] is None
    assert response.json()["error"]["upstream_status"] == 404


def test_an_invalid_cursor_400_propagates_rather_than_becoming_a_first_page(
    client: TestClient, upstream: FakeUpstream
) -> None:
    upstream.status_code = 400
    upstream.json_body = {"detail": "cursor is not valid base64: 'nope'"}
    _auth(client)
    response = client.get(
        "/v1/agents/38a83c86-0000-0000-0000-000000000000/activity?cursor=nope"
    )

    assert response.status_code == 400
    assert response.json()["data"] is None
    assert "cursor" in response.json()["error"]["message"]


def test_agents_requires_a_session_like_every_other_prefix(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """Unauthenticated callers must not even be able to probe that the Kernel
    exists behind the gateway."""
    response = client.get("/v1/agents")

    assert response.status_code == 401
    assert upstream.calls == [], "an unauthenticated request reached the upstream"


def test_the_kernels_internal_surface_is_not_routable(
    client: TestClient, upstream: FakeUpstream
) -> None:
    """AC-2, extended to the newest upstream.

    Two distinct properties, and it is worth being precise about which is
    which. The gateway serves its **own** `/internal/readiness` locally -- that
    is its health router, and it answers 200 (see
    `test_health_needs_no_session`). What must never happen is that an
    `/internal` path is *forwarded*: the route table refuses any prefix outside
    `/v1/` at construction, so no upstream is ever asked.

    And `/v1/agents/internal/health` is an ordinary path segment under the
    Kernel's `/v1` subtree, forwarded verbatim (D-6, no rewriting). It reaches
    the Kernel's router as an unknown `/v1` path, never its `/internal` tree.
    """
    _auth(client)

    before = len(upstream.calls)
    assert client.get("/internal/readiness").status_code == 200
    assert len(upstream.calls) == before, "an /internal path was forwarded upstream"

    client.get("/v1/agents/internal/health")
    assert upstream.calls[-1]["url"] == (
        "http://agent-os-kernel:8000/v1/agents/internal/health"
    ), "an /internal path must not be rewritten onto the Kernel's internal tree"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_mutating_verbs_on_agents_reach_no_upstream_unauthenticated(
    client: TestClient, upstream: FakeUpstream, method: str
) -> None:
    """The gateway forwards whatever verb it is given, so the read-only
    guarantee lives in the Kernel (asserted in its own suite, where every
    `/v1/agents` route is a GET). What must hold *here* is that an
    unauthenticated mutation attempt never reaches an upstream at all."""
    response = getattr(client, method)("/v1/agents")

    assert response.status_code == 401
    assert upstream.calls == []


def test_the_route_table_fronts_no_other_agent_os_component() -> None:
    """`agent-os/registry` and `agent-os/supervisors` have no `/v1` surface
    and must not be fronted. The Agents panel reaches packages through the
    Kernel, which asks Registry over the bus (ADR-004)."""
    from nova_api_gateway.domain.routing import build_route_table

    table = build_route_table(
        communication_engine_url="http://c:8000",
        planning_engine_url="http://p:8000",
        reasoning_engine_url="http://r:8000",
        capability_engine_url="http://cap:8000",
        action_engine_url="http://a:8000",
        agent_os_kernel_url="http://agent-os-kernel:8000",
    )
    upstreams = {route.upstream_name for route in table.routes}

    assert "agent-os-kernel" in upstreams
    assert "agent-os-registry" not in upstreams
    assert "agent-os-supervisors" not in upstreams
    assert {route.prefix for route in table.routes} == {
        "/v1/communication",
        "/v1/plans",
        "/v1/reasoning",
        "/v1/capabilities",
        "/v1/action",
        "/v1/agents",
    }

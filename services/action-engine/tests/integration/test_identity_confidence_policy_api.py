"""**CF-9's write surface through `create_app()`** — Phase 4F.4.

The contract half of the slice: routes, status codes, validation and the
identity boundary, against the real app wiring and a real `TestClient`. The
*persistence* half, and every claim that depends on stage 3 actually reading
what was written, is proven against real PostgreSQL in
`test_identity_confidence_policy_real_postgres.py` — a fake repository cannot
decide those.

The security-relevant assertions here are the negative ones. A write surface for
an authorization threshold that quietly accepted a too-permissive or
unsatisfiable value would pass every happy-path test and still be a defect.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_action_engine.api.identity_confidence_policy import MAX_CONFIGURABLE_CONFIDENCE
from nova_action_engine.config import Settings
from nova_action_engine.main import create_app

from tests.fakes.capability_port import FakeCapabilityPort
from tests.fakes.communication_port import FakeCommunicationPort
from tests.fakes.identity_port import FakeIdentityPort
from tests.fakes.repository import FakeActionRepository

ROUTE = "/v1/action/identity-confidence-policy"

_PRIMARY_USER_ID = uuid4()


@pytest.fixture
def harness(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repository = FakeActionRepository()
    app = create_app(
        Settings(primary_user_id=_PRIMARY_USER_ID),
        repository=repository,
        capability_port=FakeCapabilityPort(),
        communication_port=FakeCommunicationPort(),
        identity_port=FakeIdentityPort(),
    )
    with TestClient(app) as client:
        yield client, repository


# --- the surface exists and round-trips -------------------------------------


def test_get_returns_404_when_no_policy_is_configured(harness) -> None:  # type: ignore[no-untyped-def]
    """**404, not an empty policy.** "No policy" means threshold 1.0 at every
    tier; an empty body would render that as "a policy with nothing in it"."""
    client, _ = harness
    assert client.get(ROUTE).status_code == 404


def test_put_creates_a_policy_and_get_reads_it_back(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness

    created = client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})
    assert created.status_code == 200, created.text
    assert created.json()["minimum_confidence_by_risk"] == {"low": 0.5}

    fetched = client.get(ROUTE)
    assert fetched.status_code == 200
    assert fetched.json()["minimum_confidence_by_risk"] == {"low": 0.5}


def test_put_is_an_idempotent_upsert_not_a_duplicate(harness) -> None:  # type: ignore[no-untyped-def]
    """The table holds one row per user, so a second PUT must update rather
    than fail on the primary key or create a second row."""
    client, repository = harness

    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})
    second = client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.6}})

    assert second.status_code == 200
    assert second.json()["minimum_confidence_by_risk"] == {"low": 0.6}
    assert len(repository.identity_confidence_policies) == 1


def test_put_replaces_the_map_wholesale_rather_than_merging(harness) -> None:  # type: ignore[no-untyped-def]
    """**Removing a tier has to be expressible**, because omitting a tier is how
    an operator returns it to the fail-closed 1.0 default. A merge would make
    that impossible."""
    client, _ = harness

    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5, "moderate": 0.6}})
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    assert client.get(ROUTE).json()["minimum_confidence_by_risk"] == {"low": 0.5}


def test_an_empty_map_is_accepted_and_is_not_the_same_as_no_row(harness) -> None:  # type: ignore[no-untyped-def]
    """Deliberate: an empty map leaves every tier at 1.0, reached on purpose
    rather than by never having configured anything."""
    client, _ = harness
    assert client.put(ROUTE, json={"minimum_confidence_by_risk": {}}).status_code == 200
    assert client.get(ROUTE).status_code == 200


def test_delete_removes_the_policy_and_then_404s(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    assert client.delete(ROUTE).status_code == 204
    assert client.get(ROUTE).status_code == 404
    assert repository.identity_confidence_policies == {}


def test_delete_with_no_policy_is_a_404(harness) -> None:  # type: ignore[no-untyped-def]
    client, _ = harness
    assert client.delete(ROUTE).status_code == 404


# --- the identity boundary --------------------------------------------------


def test_the_stored_identity_is_the_servers_own(harness) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    assert list(repository.identity_confidence_policies) == [_PRIMARY_USER_ID]


def test_a_client_supplied_user_id_cannot_control_the_target_identity(harness) -> None:  # type: ignore[no-untyped-def]
    """**The security property.** `user_id` is not a field on the request model,
    so a hostile body cannot reach the stored row's identity — it is
    unrepresentable rather than merely rejected."""
    client, repository = harness
    hostile = uuid4()

    response = client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": 0.5}, "user_id": str(hostile)},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(_PRIMARY_USER_ID)
    assert hostile not in repository.identity_confidence_policies
    assert list(repository.identity_confidence_policies) == [_PRIMARY_USER_ID]


def test_cross_user_access_is_structurally_impossible() -> None:
    """There is no route parameter, query parameter or body field naming a user,
    so there is no address at which another user's policy could be reached.

    Asserted over the router's own real route table: if a later edit adds
    `/{user_id}`, this fails rather than quietly opening a cross-user surface.
    """
    from nova_action_engine.api.identity_confidence_policy import router

    paths = [route.path for route in router.routes]  # type: ignore[attr-defined]

    assert paths, "the policy routes are not mounted"
    for path in paths:
        assert path.endswith(ROUTE), f"unexpected policy route {path}"
        assert "{" not in path, f"{path} takes a path parameter; identity must be server-side"


def test_the_request_model_has_no_user_id_field() -> None:
    """The structural form of the control above, so a later edit that adds the
    field fails here rather than silently opening a forgery path."""
    from nova_action_engine.api.identity_confidence_policy import (
        IdentityConfidencePolicyRequest,
    )

    assert "user_id" not in IdentityConfidencePolicyRequest.model_fields


# --- validation: invalid input must not mutate state ------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"minimum_confidence_by_risk": {"catastrophic": 0.5}},
        {"minimum_confidence_by_risk": {"LOW": 0.5}},
        {"minimum_confidence_by_risk": {"": 0.5}},
    ],
)
def test_an_unknown_risk_tier_is_rejected_and_stores_nothing(harness, body) -> None:  # type: ignore[no-untyped-def]
    """An unrecognised key is silently ignored by stage 3's lookup, so storing
    one would look configured while changing nothing."""
    client, repository = harness

    assert client.put(ROUTE, json=body).status_code == 422
    assert repository.identity_confidence_policies == {}


@pytest.mark.parametrize("threshold", [-0.1, 1.5, 2.0])
def test_an_out_of_range_threshold_is_rejected_and_stores_nothing(harness, threshold) -> None:  # type: ignore[no-untyped-def]
    client, repository = harness

    response = client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": threshold}})

    assert response.status_code == 422
    assert repository.identity_confidence_policies == {}


@pytest.mark.parametrize("threshold", [0.76, 0.9, 1.0])
def test_a_threshold_above_the_achievable_ceiling_is_rejected(harness, threshold) -> None:  # type: ignore[no-untyped-def]
    """**D-4F4-4 / §16.5.** No identity signal can exceed 0.75 today, so a
    higher threshold would store a policy that can never admit anything.
    Maximum strictness is expressed by omitting the tier, not by writing 1.0."""
    client, repository = harness

    response = client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": threshold}})

    assert response.status_code == 422
    assert repository.identity_confidence_policies == {}


def test_the_ceiling_boundary_itself_is_accepted(harness) -> None:  # type: ignore[no-untyped-def]
    """0.75 is achievable, so it is a legitimate configuration — the rejection
    above must be strict, not off by one."""
    client, _ = harness
    response = client.put(
        ROUTE,
        json={"minimum_confidence_by_risk": {"low": MAX_CONFIGURABLE_CONFIDENCE}},
    )
    assert response.status_code == 200


def test_a_rejected_write_does_not_disturb_an_existing_policy(harness) -> None:  # type: ignore[no-untyped-def]
    """Invalid input must not mutate state — including by clobbering a good
    policy that was already there."""
    client, _ = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})

    assert client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 9.0}}).status_code == 422

    assert client.get(ROUTE).json()["minimum_confidence_by_risk"] == {"low": 0.5}


def test_error_responses_do_not_leak_identity_or_policy_detail(harness) -> None:  # type: ignore[no-untyped-def]
    """A 404 must not disclose the configured identity, and a validation error
    must not echo the stored policy back to an unauthenticated prober."""
    client, _ = harness
    client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 0.5}})
    client.delete(ROUTE)

    not_found = client.get(ROUTE)
    assert str(_PRIMARY_USER_ID) not in not_found.text

    invalid = client.put(ROUTE, json={"minimum_confidence_by_risk": {"low": 9.0}})
    assert str(_PRIMARY_USER_ID) not in invalid.text


# --- boundaries this slice must not cross -----------------------------------


def test_the_approvals_surface_is_unaffected(harness) -> None:  # type: ignore[no-untyped-def]
    """4F.4 adds a sibling route under an existing prefix; the route that was
    already there still answers."""
    client, _ = harness
    assert client.get("/v1/action/approvals").status_code == 200


def test_stage_three_evaluation_is_untouched_by_this_slice() -> None:
    """**The central boundary, asserted structurally.** TDD 4F §22 requires
    stage 3's semantics to stay byte-identical: this slice supplies rows, it
    does not change how they are read or compared."""
    import inspect

    from nova_action_engine.domain import pipeline

    source = inspect.getsource(pipeline)
    assert "threshold = 1.0" in source, "the fail-closed default was changed or moved"
    assert "if policy is not None and risk.value in policy.minimum_confidence_by_risk:" in source
    assert "effective_confidence < threshold" in source
    # The write path must not have leaked into the evaluation path.
    for forbidden in ("upsert_identity_confidence_policy", "delete_identity_confidence_policy"):
        assert forbidden not in source, f"stage 3 now calls {forbidden}"

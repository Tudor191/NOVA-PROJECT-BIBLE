"""`/v1/autonomy/*` against the real FastAPI app -- TDD 4D §8.1, §13, §18.

Every test here boots `create_app` with its real routers and real response
models; only the repository and the trust source are fakes (ADR-033's default
tier).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.domain.models import (
    DecisionLogEntry,
    PermissionCategory,
    PermissionGrant,
    Policy,
    PolicyEffect,
    PolicyMatch,
    RiskLevel,
    Suggestion,
    SuggestionStatus,
)

from tests.fakes.repository import FakeAutonomyRepository


async def _seed_suggestion(
    repository: FakeAutonomyRepository,
    settings: Settings,
    *,
    title: str = "archive three stale branches",
    category: PermissionCategory = PermissionCategory.MODIFY,
    risk: RiskLevel = RiskLevel.LOW,
    created_at: datetime | None = None,
) -> Suggestion:
    """Test fixture data, **not production data**. 4D ships no production
    producer for suggestions -- D-4D-1 removed the Event Bus origin and TDD
    §8.1 defines no creation route -- so a test that needs one writes it
    through the repository, exactly as the Playwright spec does."""
    suggestion = Suggestion(
        user_id=settings.primary_user_id,
        category=category,
        risk=risk,
        title=title,
        created_at=created_at or datetime.now(UTC),
    )
    await repository.insert_suggestion(
        suggestion,
        DecisionLogEntry(
            subject_id=suggestion.id,
            autonomy_level=1,  # type: ignore[arg-type]
            risk=risk,
            confidence=0.0,
        ),
    )
    return suggestion


# --- Overview ---------------------------------------------------------------
def test_overview_is_one_call_and_reports_an_unconfigured_instance_honestly(
    client: TestClient,
) -> None:
    """TDD §19: *"with no policy authored and no level set, the system behaves
    exactly as it does today"*. The overview must say so rather than inventing
    defaults that look configured."""
    response = client.get("/v1/autonomy")
    assert response.status_code == 200
    body = response.json()

    assert body["level"]["level"] == 0
    assert body["level"]["name"] == "Observation Only"
    assert body["level"]["configured"] is False
    assert body["proposed_count"] == 0
    assert body["policy_count"] == 0
    assert len(body["permissions"]["categories"]) == 10
    assert all(entry["granted"] is False for entry in body["permissions"]["categories"])
    assert len(body["trust"]) == 10
    assert all(entry["score"] is None for entry in body["trust"])


def test_the_overview_never_renders_an_unknown_trust_score_as_zero(
    client: TestClient,
) -> None:
    """TDD §12: *"`None` renders as 'insufficient evidence', never as 0"*."""
    body = client.get("/v1/autonomy").json()
    assert all(entry["score"] is None for entry in body["trust"])
    assert 0 not in [entry["score"] for entry in body["trust"]]
    assert 0.0 not in [entry["score"] for entry in body["trust"]]


# --- Negative control 12 -----------------------------------------------------
def test_control_12_a_degraded_trust_source_is_named_not_silently_empty(
    settings: Settings, repository: FakeAutonomyRepository
) -> None:
    """**Negative control 12.** The shipped adapter reports the conversational
    trust input as unavailable; the overview must surface that as a named
    degradation, not as an ordinary empty result."""
    from nova_autonomy_engine.clients.conversational_trust import (
        UnavailableConversationalTrustSource,
    )
    from nova_autonomy_engine.main import create_app

    app = create_app(
        settings, repository=repository, trust_source=UnavailableConversationalTrustSource()
    )
    with TestClient(app) as degraded_client:
        body = degraded_client.get("/v1/autonomy").json()

    assert body["degraded"] == ["conversational_trust"]
    assert all(entry["status"] == "unavailable" for entry in body["trust"])
    assert all(entry["detail"] for entry in body["trust"])
    assert all(entry["score"] is None for entry in body["trust"])


def test_no_data_and_unavailable_are_different_answers(client: TestClient) -> None:
    """The fake defaults to `NO_DATA`, and that must not be reported as a
    degradation -- otherwise "degraded" would mean nothing."""
    body = client.get("/v1/autonomy").json()
    assert body["degraded"] == []
    assert all(entry["status"] == "no_data" for entry in body["trust"])


# --- Level ------------------------------------------------------------------
def test_the_level_selector_offers_zero_one_and_a_disabled_two(client: TestClient) -> None:
    """TDD §12: *"0 and 1 selectable; 2 visibly present and disabled"*. Levels
    3-5 are not rendered."""
    options = client.get("/v1/autonomy/level").json()["options"]
    assert [(option["level"], option["selectable"]) for option in options] == [
        (0, True),
        (1, True),
        (2, False),
    ]
    assert [option["name"] for option in options] == ["Observation Only", "Suggestive", "Assisted"]
    assert options[2]["note"]


@pytest.mark.parametrize("level", [0, 1])
def test_levels_zero_and_one_can_be_set(client: TestClient, level: int) -> None:
    response = client.put("/v1/autonomy/level", json={"level": level})
    assert response.status_code == 200
    assert response.json()["level"] == level
    assert response.json()["configured"] is True


@pytest.mark.parametrize("level", [2, 3, 4, 5])
def test_levels_two_to_five_are_rejected_with_422_and_a_reason(
    client: TestClient, level: int
) -> None:
    """TDD §13: *"Level set to 2-5 -> **422** with the reason. Not silently
    clamped."*"""
    response = client.put("/v1/autonomy/level", json={"level": level})
    assert response.status_code == 422
    assert str(level) in response.json()["detail"]
    # And nothing was stored.
    assert client.get("/v1/autonomy/level").json()["configured"] is False


def test_level_two_is_refused_as_defined_but_not_yet_enabled(client: TestClient) -> None:
    """The reason must distinguish Level 2 from a level that does not exist."""
    detail = client.put("/v1/autonomy/level", json={"level": 2}).json()["detail"]
    assert "4F" in detail
    assert "D-1" in detail

    detail = client.put("/v1/autonomy/level", json={"level": 4}).json()["detail"]
    assert "no defined semantics" in detail


def test_a_level_outside_the_vocabulary_is_a_422_not_a_500(client: TestClient) -> None:
    assert client.put("/v1/autonomy/level", json={"level": 9}).status_code == 422
    assert client.put("/v1/autonomy/level", json={"level": -1}).status_code == 422


# --- Policies ---------------------------------------------------------------
def test_policies_round_trip_through_create_list_patch_and_delete(client: TestClient) -> None:
    created = client.post(
        "/v1/autonomy/policies",
        json={
            "name": "never delete files automatically",
            "effect": "deny",
            "match_category": "delete",
        },
    )
    assert created.status_code == 201
    policy_id = created.json()["id"]

    assert len(client.get("/v1/autonomy/policies").json()) == 1

    patched = client.patch(f"/v1/autonomy/policies/{policy_id}", json={"enabled": False})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["name"] == "never delete files automatically"

    assert client.delete(f"/v1/autonomy/policies/{policy_id}").status_code == 204
    assert client.get("/v1/autonomy/policies").json() == []


def test_an_allow_effect_is_not_accepted(client: TestClient) -> None:
    """There is no `allow` effect in 4D (TDD §6), so the schema rejects it
    rather than storing a value nothing can act on."""
    response = client.post("/v1/autonomy/policies", json={"name": "x", "effect": "allow"})
    assert response.status_code == 422


def test_an_unknown_field_fails_the_parse_rather_than_being_dropped(
    client: TestClient,
) -> None:
    """TDD §12's strict-schema rule, in both directions."""
    response = client.post(
        "/v1/autonomy/policies",
        json={"name": "x", "effect": "deny", "prioritise": "high"},
    )
    assert response.status_code == 422


def test_patching_an_unknown_policy_is_a_404(client: TestClient) -> None:
    patched = client.patch(f"/v1/autonomy/policies/{uuid4()}", json={"enabled": False})
    assert patched.status_code == 404
    assert client.delete(f"/v1/autonomy/policies/{uuid4()}").status_code == 404


# --- Permission matrix ------------------------------------------------------
def test_the_matrix_always_reports_all_ten_categories_in_the_bibles_order(
    client: TestClient,
) -> None:
    matrix = client.get("/v1/autonomy/permissions").json()
    categories = [entry["category"] for entry in matrix["categories"]]
    assert categories == [
        "read",
        "analyze",
        "recommend",
        "create",
        "modify",
        "delete",
        "execute",
        "deploy",
        "purchase",
        "communicate",
    ]


def test_setting_one_category_leaves_the_others_alone_rather_than_widening_them(
    client: TestClient,
) -> None:
    """A partial write must never reset unnamed categories to a permissive
    default -- that would be the privilege-escalation shape TDD §10 item 6
    forbids."""
    response = client.put(
        "/v1/autonomy/permissions",
        json={
            "grants": [
                {
                    "category": "read",
                    "max_risk": "moderate",
                    "requires_approval_above": None,
                    "granted": True,
                }
            ]
        },
    )
    assert response.status_code == 200
    by_category = {entry["category"]: entry for entry in response.json()["categories"]}
    assert by_category["read"]["max_risk"] == "moderate"
    assert by_category["read"]["granted"] is True
    assert by_category["delete"]["granted"] is False
    assert by_category["delete"]["max_risk"] is None


# --- Suggestions ------------------------------------------------------------
def test_an_empty_inbox_is_a_healthy_empty_state_not_an_error(client: TestClient) -> None:
    """TDD §12: *"An empty inbox is a healthy empty state ... never seeded
    suggestions."*"""
    response = client.get("/v1/autonomy/suggestions")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_there_is_no_route_that_creates_a_suggestion(client: TestClient) -> None:
    """TDD §8.1's table defines none, and inventing one because it would be
    convenient is exactly what this milestone was told not to do. The
    consequence is disclosed rather than worked around."""
    assert client.post("/v1/autonomy/suggestions", json={}).status_code in (404, 405)


def test_the_only_routes_are_the_ones_the_tdd_names(client: TestClient) -> None:
    """A guard against scope creep: **every** `/v1/autonomy` operation this
    service publishes must appear in TDD §8.1's table, and nothing else.

    Asserted against the OpenAPI document rather than the route objects,
    because that document is what `api-gateway` forwards and what a client
    reads -- an operation absent from it is not part of the contract, and one
    present in it is, however it was registered."""
    published = {
        (method.upper(), path)
        for path, operations in client.get("/openapi.json").json()["paths"].items()
        for method in operations
        if path.startswith("/v1/autonomy")
    }
    assert published == {
        ("GET", "/v1/autonomy"),
        ("GET", "/v1/autonomy/suggestions"),
        ("POST", "/v1/autonomy/suggestions/{suggestion_id}/decide"),
        ("GET", "/v1/autonomy/level"),
        ("PUT", "/v1/autonomy/level"),
        ("GET", "/v1/autonomy/policies"),
        ("POST", "/v1/autonomy/policies"),
        ("PATCH", "/v1/autonomy/policies/{policy_id}"),
        ("DELETE", "/v1/autonomy/policies/{policy_id}"),
        ("GET", "/v1/autonomy/permissions"),
        ("PUT", "/v1/autonomy/permissions"),
    }


def test_no_identity_confidence_policy_route_exists(client: TestClient) -> None:
    """**Negative control 9**, route half. CF-9 stays open and `action-engine`
    keeps sole ownership of `IdentityConfidencePolicy` (D-4D-2)."""
    document = client.get("/openapi.json").json()
    assert not [
        path
        for path in document["paths"]
        if "identity" in path or "confidence" in path
    ]
    assert not [
        name
        for name in document.get("components", {}).get("schemas", {})
        if "IdentityConfidence" in name
    ]


async def test_a_listed_suggestion_reports_which_gates_it_passes(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """TDD §12: *"each suggestion shows what is proposed, its risk, **which
    gates passed**"*."""
    await _seed_suggestion(repository, settings)
    item = client.get("/v1/autonomy/suggestions").json()["items"][0]

    # No grant -> the permission gate denies, and says so.
    assert item["gates"]["denied"] is True
    assert item["gates"]["gate"] == "permission"
    assert "absent grant" in item["gates"]["reason"]


async def test_the_gate_report_reflects_policies_authored_after_the_suggestion(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """A policy is *"absolute unless modified by the user"*, so it applies to a
    suggestion that predates it -- otherwise authoring a policy would leave
    already-proposed suggestions unaffected."""
    await _seed_suggestion(repository, settings)
    await repository.upsert_permission_grants(
        settings.primary_user_id,
        [
            PermissionGrant(
                user_id=settings.primary_user_id,
                category=PermissionCategory.MODIFY,
                max_risk=RiskLevel.CRITICAL,
            )
        ],
    )
    assert client.get("/v1/autonomy/suggestions").json()["items"][0]["gates"]["denied"] is False

    await repository.create_policy(
        Policy(
            user_id=settings.primary_user_id,
            name="freeze the repository",
            effect=PolicyEffect.DENY,
            match=PolicyMatch(category=PermissionCategory.MODIFY),
        )
    )
    gates = client.get("/v1/autonomy/suggestions").json()["items"][0]["gates"]
    assert gates["denied"] is True
    assert gates["gate"] == "policy"


async def test_suggestions_paginate_on_a_cursor_with_no_offset_parameter(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    base = datetime.now(UTC)
    for index in range(5):
        await _seed_suggestion(
            repository, settings, title=f"s{index}", created_at=base - timedelta(minutes=index)
        )

    first = client.get("/v1/autonomy/suggestions?limit=2").json()
    assert len(first["items"]) == 2
    assert first["next_cursor"]

    second = client.get(
        f"/v1/autonomy/suggestions?limit=2&cursor={first['next_cursor']}"
    ).json()
    assert len(second["items"]) == 2
    assert {item["id"] for item in first["items"]}.isdisjoint(
        {item["id"] for item in second["items"]}
    )

    # An offset parameter simply is not part of the contract.
    assert "offset" not in client.get("/v1/autonomy/suggestions").json()


def test_a_cursor_this_service_did_not_mint_is_a_422(client: TestClient) -> None:
    assert client.get("/v1/autonomy/suggestions?cursor=notacursor").status_code == 422


# --- AC-5: the decision control ---------------------------------------------
async def test_ac5_approving_requires_an_explicit_decision_and_executes_nothing(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """**AC-5.** *"executing it requires explicit user approval"* -- and the
    approval itself executes nothing."""
    suggestion = await _seed_suggestion(repository, settings)
    await repository.upsert_permission_grants(
        settings.primary_user_id,
        [
            PermissionGrant(
                user_id=settings.primary_user_id,
                category=PermissionCategory.MODIFY,
                max_risk=RiskLevel.CRITICAL,
            )
        ],
    )

    response = client.post(
        f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "approve"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"]["status"] == "approved"
    assert body["executed"] is False
    assert body["outcome"] != "execute"


async def test_ac5_a_decision_with_no_body_is_refused(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """An approval must be **stated**, never inferred from an empty body."""
    suggestion = await _seed_suggestion(repository, settings)
    response = client.post(f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={})
    assert response.status_code == 422


async def test_ac5_a_second_decision_is_a_409_and_the_first_stands(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """TDD §13: *"Second decision is a **409**; the first stands."*"""
    suggestion = await _seed_suggestion(repository, settings)
    first = client.post(
        f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "reject"}
    )
    assert first.status_code == 200

    second = client.post(
        f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "approve"}
    )
    assert second.status_code == 409

    stored = await repository.get_suggestion(settings.primary_user_id, suggestion.id)
    assert stored is not None
    assert stored.status is SuggestionStatus.REJECTED


async def test_ac5_both_decision_attempts_reach_the_append_only_log(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """TDD §13: *"The decision log is append-only and records both attempts."*"""
    suggestion = await _seed_suggestion(repository, settings)
    client.post(f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "reject"})
    client.post(f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "approve"})

    entries = await repository.list_decision_log(subject_id=suggestion.id)
    assert len(entries) == 3  # the seeding proposal, plus both attempts


async def test_approving_a_policy_denied_suggestion_is_refused_and_leaves_it_proposed(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """Bible Part 14: *"Policies remain absolute unless modified by the
    user."* An approval authored before a policy must not outrank it."""
    suggestion = await _seed_suggestion(repository, settings)
    await repository.create_policy(
        Policy(
            user_id=settings.primary_user_id,
            name="freeze the repository",
            effect=PolicyEffect.DENY,
            match=PolicyMatch(category=PermissionCategory.MODIFY),
        )
    )

    response = client.post(
        f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "approve"}
    )
    assert response.status_code == 409
    assert "policy" in response.json()["detail"]

    stored = await repository.get_suggestion(settings.primary_user_id, suggestion.id)
    assert stored is not None
    assert stored.status is SuggestionStatus.PROPOSED


async def test_rejecting_a_denied_suggestion_is_always_permitted(
    client: TestClient, repository: FakeAutonomyRepository, settings: Settings
) -> None:
    """A denial can always be acknowledged; refusing the rejection too would
    leave the user unable to clear their own inbox."""
    suggestion = await _seed_suggestion(repository, settings)
    response = client.post(
        f"/v1/autonomy/suggestions/{suggestion.id}/decide", json={"decision": "reject"}
    )
    assert response.status_code == 200


def test_deciding_an_unknown_suggestion_is_a_404(client: TestClient) -> None:
    """TDD §13, *"distinguished from a valid suggestion with no gates
    recorded"*."""
    response = client.post(
        f"/v1/autonomy/suggestions/{uuid4()}/decide", json={"decision": "approve"}
    )
    assert response.status_code == 404


def test_a_decision_other_than_approve_or_reject_is_refused(client: TestClient) -> None:
    response = client.post(
        f"/v1/autonomy/suggestions/{uuid4()}/decide", json={"decision": "execute"}
    )
    assert response.status_code == 422

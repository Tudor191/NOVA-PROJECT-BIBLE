"""`/v1/digital-twin/domains*` against the real app -- TDD 4E Sec14.2.

The **real** `create_app`, with its real routers, real schemas and real lifespan;
only the repository port is substituted, which is ADR-033's default tier. Every
line of routing and serialisation is exercised, including every `empty` and
`partially_populated` path, without Docker.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nova_contracts import PrivacyLevel
from nova_digital_twin_engine.config import Settings
from nova_digital_twin_engine.domain.derivation import evidence_from_memory_created
from nova_digital_twin_engine.domain.models import PART_16_DOMAIN_ORDER
from nova_digital_twin_engine.main import create_app

from tests.fakes.repository import FakeDigitalTwinRepository

USER = Settings().primary_user_id
"""ADR-025's single trusted user. The routes take no `user_id` -- they resolve it
from `settings.primary_user_id` server-side, exactly as `/v1/autonomy/*` does --
so the seeding below has to use the same identity the app will."""


def _run(coro: Coroutine[object, object, None]) -> None:
    """Seed from a synchronous test. `TestClient` drives its own loop, so these
    tests stay sync and the async seeding runs in a loop of its own -- the fake
    repository is plain in-memory state with no loop affinity."""
    asyncio.run(coro)


@pytest.fixture(autouse=True)
def _in_memory_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")


@pytest.fixture
def repository() -> FakeDigitalTwinRepository:
    return FakeDigitalTwinRepository()


@pytest.fixture
def app(repository: FakeDigitalTwinRepository) -> FastAPI:
    return create_app(Settings(), repository=repository)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


async def _seed_project_memories(
    repository: FakeDigitalTwinRepository,
    *,
    project_id: UUID,
    ages_in_days: tuple[float, ...],
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL,
    memory_type: str = "project",
) -> None:
    """Fold real evidence in through the same function the subscriber uses, so a
    test never constructs an evidence row the production path could not."""
    from nova_digital_twin_engine import domain_derivation

    now = datetime.now(UTC)
    for age in ages_in_days:
        rows = evidence_from_memory_created(
            user_id=USER,
            memory_id=uuid4(),
            memory_type=memory_type,
            privacy_level=privacy_level,
            project_id=project_id,
            knowledge_node_id=None,
            source_created_at=now - timedelta(days=age),
            observed_at=now,
        )
        await domain_derivation.record_evidence(repository, rows, user_id=USER)


# --- GET /domains -----------------------------------------------------------


def test_the_domain_list_renders_all_eleven_part_16_domains_in_order(
    client: TestClient,
) -> None:
    body = client.get("/v1/digital-twin/domains").json()

    assert [d["domain"] for d in body["domains"]] == [d.value for d in PART_16_DOMAIN_ORDER]
    assert len(body["domains"]) == 11, "the panel shows the Digital Twin, not one milestone"


def test_every_unpopulated_domain_carries_a_machine_readable_reason(
    client: TestClient,
) -> None:
    """Sec14.5 control 10, over the wire. A reason the panel cannot branch on is
    a comment, not a contract."""
    body = client.get("/v1/digital-twin/domains").json()

    for domain in body["domains"]:
        if domain["state"] == "populated":
            assert domain["reason"] is None
        else:
            assert domain["reason"] is not None, domain["domain"]
            assert domain["reason"]["code"], domain["domain"]
            assert domain["reason"]["detail"], domain["domain"]


def test_a_fresh_install_reports_the_two_4f_domains_as_empty_with_no_source_engine(
    client: TestClient,
) -> None:
    body = client.get("/v1/digital-twin/domains").json()
    by_name = {d["domain"]: d for d in body["domains"]}

    for name in ("software_environment", "hardware_environment"):
        assert by_name[name]["state"] == "empty"
        assert by_name[name]["reason"]["code"] == "no_source_engine"
        assert by_name[name]["facts"] == {}
        assert by_name[name]["unavailable_fields"], (
            "a domain with no source should still name what it would hold"
        )


def test_the_two_shipped_2dd_domains_are_marked_as_such(client: TestClient) -> None:
    body = client.get("/v1/digital-twin/domains").json()
    shipped = {d["domain"] for d in body["domains"] if d["shipped_before_4e"]}

    assert shipped == {"communication_style", "preferences"}


# --- GET /domains/{domain} and refresh --------------------------------------


def test_one_domain_can_be_read_by_name(client: TestClient) -> None:
    response = client.get(
        "/v1/digital-twin/domains/goals"
    )

    assert response.status_code == 200
    assert response.json()["domain"] == "goals"


def test_an_unknown_domain_is_a_404_naming_the_eleven(client: TestClient) -> None:
    response = client.get(
        "/v1/digital-twin/domains/telepathy"
    )

    assert response.status_code == 404
    assert "personal_workflow" in response.json()["detail"]


def test_refreshing_a_domain_with_no_evidence_succeeds_and_reports_empty(
    client: TestClient,
) -> None:
    """"There is nothing to derive" is an answer, not an error."""
    response = client.post(
        "/v1/digital-twin/domains/skill_profile/refresh"
    )

    assert response.status_code == 200
    assert response.json()["state"] == "empty"
    assert response.json()["reason"]["code"] == "no_evidence_observed"


def test_refresh_re_derives_from_this_engines_own_accumulated_evidence(
    client: TestClient, repository: FakeDigitalTwinRepository
) -> None:
    """ADR-004: the accumulated evidence is the only source this engine owns
    (Sec0.1.5). Refresh recomputes a model; it fetches no raw data."""
    project_id = uuid4()
    _run(_seed_project_memories(repository, project_id=project_id, ages_in_days=(40.0, 10.0)))

    body = client.post(
        "/v1/digital-twin/domains/projects/refresh"
    ).json()

    assert body["state"] == "populated"
    assert body["evidence_count"] == 2
    assert body["facts"]["project_count"] == 1


# --- GET /domains/projects and the AC-6 detail route -------------------------


def test_the_projects_route_returns_both_the_domain_and_the_project_list(
    client: TestClient, repository: FakeDigitalTwinRepository
) -> None:
    """`projects` is both a Part 16 domain and a collection; the concrete route
    wins by declaration order, so it returns both rather than shadowing one."""
    project_id = uuid4()
    _run(_seed_project_memories(repository, project_id=project_id, ages_in_days=(5.0,)))

    body = client.get(
        "/v1/digital-twin/domains/projects"
    ).json()

    assert body["domain"]["domain"] == "projects"
    assert [p["project_id"] for p in body["projects"]] == [str(project_id)]


def test_the_ac6_route_reconstructs_a_multi_week_gap_from_persisted_timestamps(
    client: TestClient, repository: FakeDigitalTwinRepository
) -> None:
    """**AC-6 at the HTTP boundary.** The gap is computed from the timestamps the
    evidence carries, and nothing here simulates elapsed time."""
    project_id = uuid4()
    _run(
        _seed_project_memories(
            repository, project_id=project_id, ages_in_days=(75.0, 60.0, 31.0)
        )
    )

    body = client.get(
        f"/v1/digital-twin/domains/projects/{project_id}"
    ).json()

    project = body["project"]
    assert project["memory_count"] == 3
    assert project["gap_days"] == pytest.approx(31.0, abs=0.01)
    assert project["gap_days"] > 21, "a multi-week gap must read as multi-week"
    assert project["first_activity_at"] < project["last_activity_at"]


def test_an_unknown_project_is_a_404_not_an_empty_project(client: TestClient) -> None:
    """A project that does not exist and a project with no activity are different
    answers. Returning zeros for the first would invent the second."""
    response = client.get(
        f"/v1/digital-twin/domains/projects/{uuid4()}"
    )

    assert response.status_code == 404
    assert "project_id" in response.json()["detail"]


def test_a_restricted_memory_never_reaches_the_rendered_project_list(
    client: TestClient, repository: FakeDigitalTwinRepository
) -> None:
    """Sec14.5 control 6 at the rendering edge. The row was never created, so
    there is nothing here to filter."""
    project_id = uuid4()
    _run(
        _seed_project_memories(
            repository,
            project_id=project_id,
            ages_in_days=(5.0,),
            privacy_level=PrivacyLevel.HIGHLY_SENSITIVE,
        )
    )

    body = client.get(
        "/v1/digital-twin/domains/projects"
    ).json()

    assert body["projects"] == []
    assert body["domain"]["state"] == "empty"

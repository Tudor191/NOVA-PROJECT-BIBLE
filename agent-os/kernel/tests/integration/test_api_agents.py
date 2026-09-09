"""The Kernel's read-only `/v1/agents` surface -- Phase 4C milestone 4C.2c.

Exercised through a real `create_app()` and a real `TestClient`, so the router
registration, the response models and FastAPI's own validation are all in the
path. The Registry side is a purpose-built fake `RegistryPort` rather than a
real bus: what these tests are about is what the *endpoint* does with what
Registry returns -- including what it does when Registry raises -- and that is
independent of any broker. The RPC's own wire behaviour is covered against a
real bus in `agent-os/registry`'s `test_events_list_packages_request.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from nova_agent_os_kernel.config import Settings
from nova_agent_os_kernel.domain.activity import (
    AgentActivity,
    AgentActivityKind,
    encode_cursor,
)
from nova_agent_os_kernel.domain.models import AgentInstance
from nova_agent_os_kernel.main import create_app
from nova_contracts import AgentPackageSnapshot

from tests.fakes.repository import FakeKernelRepository

_BASE = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


class _StubRegistryPort:
    """Answers `list_packages()` with a fixed result, or raises."""

    def __init__(
        self,
        *,
        packages: list[AgentPackageSnapshot] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self._packages = packages if packages is not None else []
        self._error = error

    async def find_healthy_package(self, **_kwargs: object) -> AgentPackageSnapshot | None:
        return None

    async def list_packages(self, **_kwargs: object) -> list[AgentPackageSnapshot]:
        if self._error is not None:
            raise self._error
        return list(self._packages)


def _snapshot(category: str = "coding", version: str = "1.2.0") -> AgentPackageSnapshot:
    return AgentPackageSnapshot(
        id=uuid4(),
        category=category,
        version=version,
        manifest_json={"id": f"{category}-agent", "version": version},
        health_status="healthy",
    )


def _instance(**overrides: object) -> AgentInstance:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "agent_package_id": uuid4(),
        "category": "coding",
        "execution_backend": "inprocess",
        "status": "running",
        "started_at": _BASE,
        "health_status": "unknown",
    }
    defaults.update(overrides)
    return AgentInstance(**defaults)  # type: ignore[arg-type]


def _activity(instance_id: UUID, **overrides: object) -> AgentActivity:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "agent_instance_id": instance_id,
        "occurred_at": _BASE,
        "kind": AgentActivityKind.DISPATCHED,
        "correlation_id": None,
        "detail": {},
    }
    defaults.update(overrides)
    return AgentActivity(**defaults)  # type: ignore[arg-type]


def _client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repository: FakeKernelRepository | None = None,
    registry: _StubRegistryPort | None = None,
) -> tuple[TestClient, FakeKernelRepository]:
    monkeypatch.setenv("EVENT_BUS_BACKEND", "in_memory")
    repo = repository or FakeKernelRepository()
    app = create_app(
        Settings(),
        repository=repo,
        registry_port=registry or _StubRegistryPort(),  # type: ignore[arg-type]
    )
    return TestClient(app), repo


# --- GET /v1/agents ---------------------------------------------------------


def test_lists_the_real_registered_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    """The five Agent Packages Registry really discovers from `agents/`, named
    here rather than invented -- these are the categories that exist on disk."""
    packages = [
        _snapshot("architect", "0.1.0"),
        _snapshot("coding", "0.1.0"),
        _snapshot("documentation", "0.1.0"),
        _snapshot("qa", "0.1.0"),
        _snapshot("research", "0.1.0"),
    ]
    client, _ = _client(monkeypatch, registry=_StubRegistryPort(packages=packages))

    with client:
        response = client.get("/v1/agents")

    assert response.status_code == 200
    body = response.json()
    assert [p["category"] for p in body["packages"]] == [
        "architect",
        "coding",
        "documentation",
        "qa",
        "research",
    ]
    assert [p["manifest_id"] for p in body["packages"]] == [
        "architect-agent",
        "coding-agent",
        "documentation-agent",
        "qa-agent",
        "research-agent",
    ]


def test_the_package_view_does_not_leak_the_whole_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A projection, not the wire snapshot. `manifest_json` carries declared
    permissions and capabilities; an external read-only surface carries the
    minimum the panel renders."""
    snapshot = _snapshot()
    snapshot.manifest_json["required_permissions"] = ["filesystem", "terminal"]
    client, _ = _client(monkeypatch, registry=_StubRegistryPort(packages=[snapshot]))

    with client:
        body = client.get("/v1/agents").json()

    package = body["packages"][0]
    assert "manifest_json" not in package
    assert "required_permissions" not in package
    assert set(package) == {"id", "manifest_id", "category", "version", "health_status"}


def test_a_healthy_registry_with_no_packages_is_a_successful_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision D-1's `200 []` half."""
    client, _ = _client(monkeypatch, registry=_StubRegistryPort(packages=[]))

    with client:
        response = client.get("/v1/agents")

    assert response.status_code == 200
    assert response.json()["packages"] == []


@pytest.mark.parametrize(
    "error",
    [TimeoutError("registry did not answer"), RuntimeError("broker refused")],
    ids=["timeout", "broker-error"],
)
def test_registry_failure_is_an_explicit_503_not_an_empty_list(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    """Decision D-1's `503` half, and the most important assertion in this file.

    If this ever answered `200` with `packages: []`, the endpoint would report
    "no agents are installed" while the truth is "the Registry is down", and
    no layer above could tell the difference.
    """
    client, _ = _client(monkeypatch, registry=_StubRegistryPort(error=error))

    with client:
        response = client.get("/v1/agents")

    assert response.status_code == 503
    assert "Registry" in response.json()["detail"]


def test_a_provider_free_runtime_has_zero_instances_and_is_still_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An `agent_instance` row exists only after a Kernel dispatch, which is
    reached only from an LLM-backed planning decomposition. With no provider
    the table is legitimately empty -- a `200` with an empty list, never an
    error, and never something the panel should render as degraded."""
    client, _ = _client(monkeypatch, registry=_StubRegistryPort(packages=[_snapshot()]))

    with client:
        response = client.get("/v1/agents")

    assert response.status_code == 200
    body = response.json()
    assert body["instances"] == []
    assert body["packages"] != [], "packages are provider-free and must still appear"


def test_instances_are_returned_newest_first_with_their_real_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    older = _instance(started_at=_BASE, status="completed")
    newer = _instance(started_at=_BASE + timedelta(minutes=5), status="running")

    with client:
        # Seeded through the repository, not the API: there is no write
        # endpoint, and 4C.2c must not create one.
        for instance in (older, newer):
            _run(repository.insert(instance))
        body = client.get("/v1/agents").json()

    assert [i["id"] for i in body["instances"]] == [str(newer.id), str(older.id)]
    assert [i["status"] for i in body["instances"]] == ["running", "completed"]


def test_supervisor_topology_is_the_observed_single_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 3E ships exactly one supervisor and no supervisor identity, so
    the topology is declared rather than persisted -- and the response says so
    with `membership_is_derived`. No supervisor id is invented."""
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()

    with client:
        _run(repository.insert(instance))
        body = client.get("/v1/agents").json()

    assert len(body["supervisors"]) == 1
    supervisor = body["supervisors"][0]
    assert supervisor["category"] == "engineering"
    assert supervisor["instance_ids"] == [str(instance.id)]
    assert supervisor["membership_is_derived"] is True
    assert "id" not in supervisor, "no supervisor identity exists to report"


def test_instance_supervisor_id_is_reported_as_null_rather_than_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The column exists but no code path writes it. Surfaced as `null` so a
    reader can see it is empty rather than infer it does not exist."""
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)

    with client:
        _run(repository.insert(_instance()))
        body = client.get("/v1/agents").json()

    assert body["instances"][0]["supervisor_id"] is None


# --- GET /v1/agents/{id} ----------------------------------------------------


def test_get_by_id_returns_the_persisted_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance(status="completed", health_status="healthy")

    with client:
        _run(repository.insert(instance))
        response = client.get(f"/v1/agents/{instance.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(instance.id)
    assert body["status"] == "completed"
    assert body["health_status"] == "healthy"
    assert body["execution_backend"] == "inprocess"


def test_get_by_id_404s_for_an_unknown_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """404, never an empty object -- a client could not distinguish an empty
    object from a real instance whose fields happen to be unset."""
    client, _ = _client(monkeypatch)

    with client:
        response = client.get(f"/v1/agents/{uuid4()}")

    assert response.status_code == 404


def test_get_by_id_rejects_a_malformed_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = _client(monkeypatch)

    with client:
        response = client.get("/v1/agents/not-a-uuid")

    assert response.status_code == 422


# --- GET /v1/agents/{id}/activity -------------------------------------------


def test_activity_returns_rows_newest_first_with_correlation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`correlation_id` is first-class provenance and must reach the client,
    not be flattened into `detail`."""
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()
    correlation_id = uuid4()

    with client:
        _run(repository.insert(instance))
        _run(
            repository.append_activity(
                _activity(
                    instance.id,
                    occurred_at=_BASE,
                    kind=AgentActivityKind.DISPATCHED,
                    correlation_id=correlation_id,
                )
            )
        )
        _run(
            repository.append_activity(
                _activity(
                    instance.id,
                    occurred_at=_BASE + timedelta(minutes=1),
                    kind=AgentActivityKind.COMPLETED,
                    correlation_id=correlation_id,
                    detail={"outcome": "success"},
                )
            )
        )
        response = client.get(f"/v1/agents/{instance.id}/activity")

    assert response.status_code == 200
    body = response.json()
    assert [item["kind"] for item in body["items"]] == ["completed", "dispatched"]
    assert {item["correlation_id"] for item in body["items"]} == {str(correlation_id)}
    assert body["items"][0]["detail"] == {"outcome": "success"}
    assert body["next_cursor"] is None


def test_activity_pages_with_a_cursor_and_terminates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every row shares a timestamp, so the `(occurred_at, id)` tie-break does
    the work. No row skipped, none repeated, and the walk terminates."""
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()
    ids = {uuid4() for _ in range(5)}

    with client:
        _run(repository.insert(instance))
        for activity_id in ids:
            _run(repository.append_activity(_activity(instance.id, id=activity_id)))

        seen: list[str] = []
        cursor: str | None = None
        for _ in range(10):
            url = f"/v1/agents/{instance.id}/activity?limit=2"
            if cursor is not None:
                url += f"&cursor={cursor}"
            body = client.get(url).json()
            seen.extend(item["id"] for item in body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break

    assert cursor is None, "paging did not terminate"
    assert {UUID(value) for value in seen} == ids
    assert len(set(seen)) == len(seen), "a row was returned on two pages"


def test_a_full_page_with_no_further_rows_reports_no_next_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()

    with client:
        _run(repository.insert(instance))
        for _ in range(3):
            _run(repository.append_activity(_activity(instance.id)))
        body = client.get(f"/v1/agents/{instance.id}/activity?limit=3").json()

    assert len(body["items"]) == 3
    assert body["next_cursor"] is None


def test_an_invalid_cursor_is_a_400_not_a_silent_first_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller who asked for a specific page must not be handed rows they
    have already seen and told it succeeded."""
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()

    with client:
        _run(repository.insert(instance))
        _run(repository.append_activity(_activity(instance.id)))
        response = client.get(f"/v1/agents/{instance.id}/activity?cursor=not-a-cursor!!")

    assert response.status_code == 400
    assert response.json()["detail"]


def test_a_cursor_past_the_last_row_is_an_empty_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()

    with client:
        _run(repository.insert(instance))
        _run(repository.append_activity(_activity(instance.id, occurred_at=_BASE)))
        beyond = encode_cursor(_BASE - timedelta(days=1), UUID(int=0))
        body = client.get(f"/v1/agents/{instance.id}/activity?cursor={beyond}").json()

    assert body["items"] == []
    assert body["next_cursor"] is None


def test_activity_404s_for_an_unknown_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Checked before paging: an empty page for a nonexistent instance is
    indistinguishable from a real instance that has done nothing yet."""
    client, _ = _client(monkeypatch)

    with client:
        response = client.get(f"/v1/agents/{uuid4()}/activity")

    assert response.status_code == 404


def test_activity_is_empty_for_a_real_instance_with_no_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()

    with client:
        _run(repository.insert(instance))
        response = client.get(f"/v1/agents/{instance.id}/activity")

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.parametrize("limit", [0, -1, 201, 10_000])
def test_an_out_of_range_limit_is_rejected(
    monkeypatch: pytest.MonkeyPatch, limit: int
) -> None:
    """An append-only table is the one place an unbounded `limit` really can
    ask for everything ever recorded."""
    repository = FakeKernelRepository()
    client, _ = _client(monkeypatch, repository=repository)
    instance = _instance()

    with client:
        _run(repository.insert(instance))
        response = client.get(f"/v1/agents/{instance.id}/activity?limit={limit}")

    assert response.status_code == 422


# --- the surface is read-only -----------------------------------------------


def _openapi_paths(client: TestClient) -> dict[str, dict]:
    """Registered paths and their verbs, from the app's own OpenAPI schema.

    Read from `openapi()` rather than by walking `app.routes`: FastAPI wraps an
    included router, so the child routes are not reachable as top-level
    `route.path` values -- an inspection that walked them would find nothing
    and pass vacuously.
    """
    return client.app.openapi()["paths"]  # type: ignore[attr-defined,no-any-return]


def test_no_mutating_route_exists_on_the_agents_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural, not behavioural: every `/v1/agents` route the app registers
    must be a GET. A mutation added by accident fails here rather than being
    discovered from outside."""
    client, _ = _client(monkeypatch)
    paths = {
        path: spec
        for path, spec in _openapi_paths(client).items()
        if path.startswith("/v1/agents")
    }
    assert set(paths) == {
        "/v1/agents",
        "/v1/agents/{agent_instance_id}",
        "/v1/agents/{agent_instance_id}/activity",
    }
    for path, spec in paths.items():
        assert set(spec) <= {"get"}, f"{path} accepts {sorted(spec)}"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_mutating_verbs_are_refused(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    client, _ = _client(monkeypatch)

    with client:
        response = getattr(client, method)("/v1/agents")

    assert response.status_code == 405


def test_the_kernel_exposes_no_activity_write_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`agent_activity` is append-only and has no HTTP write path at all --
    the only writers are the Kernel's own dispatch paths (4C.2d)."""
    client, _ = _client(monkeypatch)
    activity_paths = {
        path: spec
        for path, spec in _openapi_paths(client).items()
        if path.endswith("/activity")
    }
    assert set(activity_paths) == {"/v1/agents/{agent_instance_id}/activity"}
    assert set(activity_paths["/v1/agents/{agent_instance_id}/activity"]) == {"get"}

    with client:
        assert client.post(f"/v1/agents/{uuid4()}/activity").status_code == 405


def test_internal_routes_are_untouched_by_the_new_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4C.2c adds `/v1`; `/internal/*` must still be exactly what it was."""
    client, _ = _client(monkeypatch)

    with client:
        assert client.get("/internal/health").status_code == 200
        assert client.get("/internal/readiness").status_code == 200
        # And the new surface did not accidentally shadow or expose it.
        assert client.get("/v1/agents/internal/health").status_code in (404, 422)


def _run(coroutine: object) -> object:
    """Drive a coroutine to completion from a sync test body.

    `TestClient` runs the app on its own portal; these calls seed the *fake
    repository* directly rather than going through the app, because there is
    no write endpoint to seed through -- which is the point.
    """
    import asyncio

    return asyncio.run(coroutine)  # type: ignore[arg-type]

"""The Kernel's read-only `/v1/agents` surface -- decision **D-4** (master
scope §9), implemented in Phase 4C milestone 4C.2c.

TDD 3E §4 gave this component a health-only HTTP surface, on the reasoning
that its work is Event-Bus- and internal-loop-driven. That was right for
Phase 3, in which nothing consumed a Kernel API. D-4 amends it because the
Agents panel needs point-in-time queries -- "what packages are registered",
"what is instance X doing" -- that an event stream cannot answer: a client
joining mid-stream sees no history.

**Read-only, and structurally so.** Every route here is a `GET`. No route
creates, mutates or deletes anything; agent lifecycle stays Event-Bus-driven
exactly as TDD 3E designed it, and `agent_activity` stays append-only with no
write path from HTTP at all. `tests/integration/test_api_agents.py` asserts
the absence of any non-GET method rather than trusting this paragraph.

**No envelope here.** `api-gateway` owns doc 11 §4's `{data, meta, error}`
wrapper -- its own `domain/envelope.py` records that "engines return bare
models -- none of the fourteen emits this envelope itself" -- so these
handlers return bare Pydantic models and let one layer own the convention.
Duplicating it would produce a doubly-wrapped payload the web client's
`entities/` layer could not parse.

**Reachable only through `api-gateway`.** Nothing here is exposed directly;
`/internal/*` stays unroutable (doc 11 §3) and is not touched by this module.

**Registry failure is not an empty list (decision D-1).** `GET /v1/agents`
answers `200` with `packages: []` when Registry is healthy and holds nothing,
and `503` when Registry cannot be reached. `RegistryClient` does not catch,
so the distinction survives the whole way up; converting a timeout into `[]`
here would break the rule `api-gateway`'s own envelope module states -- "a
degraded upstream must never look like an empty success" -- and would report
"no agents are installed" while the truth is "the Registry is down".
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from nova_observability import get_logger
from pydantic import BaseModel, Field

from nova_agent_os_kernel.domain.activity import InvalidCursorError

router = APIRouter(prefix="/v1/agents", tags=["agents"])

logger = get_logger("kernel.api.agents")

#: The one supervisor category Phase 3E ships (doc 12 §9, TDD 3E §7). Named
#: here rather than discovered because there is nothing to discover from:
#: `agent-os/supervisors` has no persistence, no identity and no registry, and
#: 4C's approved design (scope-mapping decision 6) is explicitly to render the
#: *observed deployment topology* rather than invent one.
_ENGINEERING_SUPERVISOR_CATEGORY = "engineering"


class AgentPackageView(BaseModel):
    """One installed Agent Package, as the Agents panel reads it.

    A **projection**, not the wire snapshot. `AgentPackageSnapshot` carries the
    whole `manifest_json`, including the package's declared permissions and
    capabilities; nothing the panel renders needs them, and an external
    read-only surface should carry the minimum. `manifest_id` is lifted out
    because it is the human-readable name (`"coding-agent"`) and the only part
    of the manifest the panel shows.
    """

    id: UUID
    manifest_id: str | None = None
    category: str
    version: str
    health_status: str


class AgentInstanceView(BaseModel):
    """One agent instance, field-for-field from `agent_os.agent_instance`."""

    id: UUID
    agent_package_id: UUID
    category: str
    execution_backend: str
    status: str
    health_status: str
    assigned_task_node_id: UUID | None = None
    supervisor_id: UUID | None = None
    """**Always `null` today, and reported honestly as such.** The column
    exists (TDD 3E §4) but no code path writes it: `agent-os/supervisors` has
    no identity to write. Surfaced rather than omitted so a reader can see
    that the field is empty instead of inferring it does not exist."""
    started_at: datetime


class SupervisorView(BaseModel):
    """The observed supervision topology: `Kernel -> Engineering Supervisor ->
    instances` (doc 12 §9's own tree).

    **This is declared deployment topology, not persisted data, and says so.**
    Phase 3E ships exactly one supervisor, so every instance is supervised by
    it by construction -- that is a true statement about the deployment, not a
    relationship read from a table. `instance_ids` therefore lists every
    instance, and `membership_is_derived` is `True` to make the basis explicit
    to any reader, including the panel.

    No supervisor id is invented. There is no supervisor identity mechanism in
    Phase 3E, and minting a UUID here would fabricate one -- which the approved
    4C design (scope-mapping §8(g), option A) explicitly rules out.
    """

    category: str
    instance_ids: list[UUID] = Field(default_factory=list)
    membership_is_derived: bool = True


class AgentsResponse(BaseModel):
    """`GET /v1/agents`.

    `packages` and `instances` come from different owners: packages are
    `agent-os/registry`'s, fetched over the bus (ADR-004 -- the Kernel never
    reads `agent_package`), and instances are the Kernel's own table. The
    Kernel assembles them because `api-gateway` forwards 1:1 to a single
    upstream and cannot fan out.
    """

    packages: list[AgentPackageView] = Field(default_factory=list)
    instances: list[AgentInstanceView] = Field(default_factory=list)
    supervisors: list[SupervisorView] = Field(default_factory=list)


class ActivityView(BaseModel):
    """One activity row. `correlation_id` is first-class provenance, carried
    through to the client rather than buried in `detail` (4C.2b)."""

    id: UUID
    agent_instance_id: UUID
    occurred_at: datetime
    kind: str
    correlation_id: UUID | None = None
    detail: dict = Field(default_factory=dict)


class ActivityPageResponse(BaseModel):
    """`GET /v1/agents/{id}/activity`. `next_cursor` is `null` exactly when
    this page is the last -- never a cursor onto an empty page."""

    items: list[ActivityView] = Field(default_factory=list)
    next_cursor: str | None = None


def _instance_view(instance: object) -> AgentInstanceView:
    return AgentInstanceView.model_validate(instance, from_attributes=True)


@router.get("", response_model=AgentsResponse)
async def list_agents(request: Request, limit: int = 50) -> AgentsResponse:
    """Registered packages, live instances, and the observed supervisor
    topology.

    **Zero instances is a healthy answer, not a degraded one.** An
    `agent_instance` row exists only after a Kernel dispatch, which is reached
    only from `planning.task_graph.created`, which `planning-engine` publishes
    only from an LLM-backed decomposition. With no model provider configured
    the table is legitimately empty -- AC-4's instance and peer-review clauses
    are Deferred by approval for exactly this reason (master scope §1.1). The
    response says so by returning `200` with an empty list; it must never be
    dressed up as an error, and the panel must not render it as one.

    Packages, by contrast, are real and populated without a provider: Registry
    discovers the five under `agents/` from disk at startup.
    """
    state = request.app.state

    try:
        packages = await state.registry_port.list_packages()
    except Exception as exc:  # noqa: BLE001 -- any RPC failure is "Registry unreachable"
        # Decision D-1. Not caught into an empty list: `200 []` means Registry
        # is healthy and holds nothing, and collapsing the two would make the
        # difference unrepresentable at every layer above this one.
        logger.warning(
            "registry list_packages RPC failed -- answering 503 rather than an "
            "empty package list",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The Agent Registry could not be reached.",
        ) from exc

    instances = await state.repository.list_instances(limit=limit)
    instance_views = [_instance_view(instance) for instance in instances]

    return AgentsResponse(
        packages=[
            AgentPackageView(
                id=package.id,
                manifest_id=package.manifest_json.get("id"),
                category=package.category,
                version=package.version,
                health_status=package.health_status,
            )
            for package in packages
        ],
        instances=instance_views,
        supervisors=[
            SupervisorView(
                category=_ENGINEERING_SUPERVISOR_CATEGORY,
                instance_ids=[view.id for view in instance_views],
            )
        ],
    )


@router.get("/{agent_instance_id}", response_model=AgentInstanceView)
async def get_agent(agent_instance_id: UUID, request: Request) -> AgentInstanceView:
    """One persisted agent instance. 404 when it does not exist -- never an
    empty object, which a client could not distinguish from a real instance
    with unset fields."""
    instance = await request.app.state.repository.find_by_id(agent_instance_id)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent instance found with id {agent_instance_id!r}",
        )
    return _instance_view(instance)


@router.get("/{agent_instance_id}/activity", response_model=ActivityPageResponse)
async def get_agent_activity(
    agent_instance_id: UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> ActivityPageResponse:
    """One page of an instance's activity, newest first.

    Keyset pagination exactly as 4C.2b implements it: ordered by
    `(occurred_at DESC, id DESC)`, `limit + 1` fetched so `next_cursor` is
    `null` precisely when no further row exists, and **no offset anywhere** --
    an offset walks rows the database has already discarded and shifts under
    concurrent inserts, which on an append-only table growing at the head
    would silently repeat rows between pages.

    An unparseable `cursor` is a **400**, never a silent restart at page one:
    a caller who asked for a specific page would otherwise be handed rows they
    had already seen, and told it succeeded.

    `limit` is bounded 1..200. `/v1/plans` and `/v1/action/approvals` take a
    bare `limit: int = 50`, and this keeps that name and default while adding
    FastAPI's own range validation -- an append-only table is the one place
    where an unbounded `limit` really can ask for everything ever recorded.

    404 when the instance is unknown, checked before paging: an empty page for
    a nonexistent instance is indistinguishable from a real instance that has
    done nothing yet.
    """
    state = request.app.state

    if await state.repository.find_by_id(agent_instance_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent instance found with id {agent_instance_id!r}",
        )

    try:
        page = await state.repository.list_activity(
            agent_instance_id, limit=limit, cursor=cursor
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return ActivityPageResponse(
        items=[
            ActivityView(
                id=item.id,
                agent_instance_id=item.agent_instance_id,
                occurred_at=item.occurred_at,
                kind=item.kind.value,
                correlation_id=item.correlation_id,
                detail=item.detail,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )

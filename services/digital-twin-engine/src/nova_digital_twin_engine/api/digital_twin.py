"""`/v1/digital-twin/domains*` -- TDD 4E Sec7's five routes, and nothing beyond them.

| Method | Path |
|---|---|
| `GET`  | `/v1/digital-twin/domains` |
| `GET`  | `/v1/digital-twin/domains/projects` |
| `GET`  | `/v1/digital-twin/domains/projects/{project_id}` |
| `GET`  | `/v1/digital-twin/domains/{domain}` |
| `POST` | `/v1/digital-twin/domains/{domain}/refresh` |

**Five, asserted against the OpenAPI document** (TDD 4E Sec14.5 control 7), and
every one of them exists because Sec13's panel or Sec16's AC-6 mapping needs it.
`POST /refresh` is the only write, and it writes only this engine's own derived
state -- never `memory-engine`'s and never `perception-engine`'s (control 4).

**`/domains/projects` is declared before `/domains/{domain}`, deliberately.**
`projects` is itself one of Part 16's eleven domains, so the two paths collide;
FastAPI resolves by declaration order, and the concrete route must win. Rather
than leave the generic read unreachable for that one domain, `/domains/projects`
returns **both** -- the `projects` domain model *and* the derived project list --
so nothing is shadowed away.

**No route creates a domain, and none accepts derived data.** The only input is
which domain to re-derive. A route that let a caller write a domain's facts would
make every negative control in Sec14.5 unprovable, since a fabricated value could
then enter through the front door.

**No `TrustMetric` route** (ratified Sec19.2): CF-10 stays open, and this module
is the obvious place it would have been closed by accident.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from nova_digital_twin_engine import domain_derivation
from nova_digital_twin_engine.domain.models import (
    PART_16_DOMAIN_ORDER,
    SHIPPED_2DD_DOMAINS,
    DomainModel,
    DomainState,
    ProjectModel,
    TwinDomain,
)

router = APIRouter(prefix="/v1/digital-twin", tags=["digital-twin-domains"])


class _Strict(BaseModel):
    """Every 4E request and response model forbids unknown fields, matching 4D.

    A response that silently accepted an extra key would let a contract drift
    reach the panel as `undefined`; `extra="forbid"` turns that into a failure at
    the boundary that introduced it."""

    model_config = ConfigDict(extra="forbid")


class DomainReasonResponse(_Strict):
    """Never a bare string. `code` is what the panel branches on and a test
    asserts; `detail` is what a person reads (TDD 4E Sec14.5 control 10)."""

    code: str
    detail: str


class DomainResponse(_Strict):
    domain: str
    state: str
    reason: DomainReasonResponse | None
    evidence_count: int
    facts: dict[str, Any]
    unavailable_fields: list[str]
    derived_at: str
    shipped_before_4e: bool
    """`true` for `communication_style` and `preferences`, which Phase 2D-D
    shipped. Rendered so an operator can tell a domain 4E derives from one it
    merely reports, without having to know the milestone history."""


class DomainListResponse(_Strict):
    domains: list[DomainResponse]
    """All **eleven** Part 16 domains in Part 16's own order -- the nine 4E adds
    and the two 2D-D shipped. A list of nine would make the panel a view of this
    milestone rather than of the Digital Twin."""


class ProjectResponse(_Strict):
    project_id: str
    memory_count: int
    memory_type_counts: dict[str, int]
    first_activity_at: str | None
    last_activity_at: str | None
    gap_days: float | None
    """Days since the newest persisted source timestamp. **`null`, never `0.0`,**
    when no evidence row carried one -- zero would read as "active today", which
    is the opposite claim."""

    derived_at: str


class ProjectListResponse(_Strict):
    domain: DomainResponse
    projects: list[ProjectResponse]


class ProjectDetailResponse(_Strict):
    """**The AC-6 surface** -- *"what was I doing on Project X"* after a gap."""

    project: ProjectResponse


def _reason(model: DomainModel) -> DomainReasonResponse | None:
    if model.reason is None:
        return None
    return DomainReasonResponse(code=model.reason.code.value, detail=model.reason.detail)


def _domain_response(model: DomainModel) -> DomainResponse:
    return DomainResponse(
        domain=model.domain.value,
        state=model.state.value,
        reason=_reason(model),
        evidence_count=model.evidence_count,
        facts=model.facts,
        unavailable_fields=model.unavailable_fields,
        derived_at=model.derived_at.isoformat(),
        shipped_before_4e=model.domain in SHIPPED_2DD_DOMAINS,
    )


def _project_response(model: ProjectModel) -> ProjectResponse:
    return ProjectResponse(
        project_id=str(model.project_id),
        memory_count=model.memory_count,
        memory_type_counts=model.memory_type_counts,
        first_activity_at=(
            model.first_activity_at.isoformat() if model.first_activity_at else None
        ),
        last_activity_at=(
            model.last_activity_at.isoformat() if model.last_activity_at else None
        ),
        gap_days=model.gap_days,
        derived_at=model.derived_at.isoformat(),
    )


def _parse_domain(raw: str) -> TwinDomain:
    try:
        return TwinDomain(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"{raw!r} is not one of Bible Part 16's eleven domains: "
                f"{', '.join(d.value for d in PART_16_DOMAIN_ORDER)}."
            ),
        ) from exc


@router.get("/domains", response_model=DomainListResponse)
async def list_domains(user_id: UUID, request: Request) -> DomainListResponse:
    """All eleven domains: name, state, reason-if-not-populated, last-derived.

    Derives on read rather than serving a possibly-stale row. The derivation is a
    bounded query over this engine's own evidence, and a panel that showed a
    domain as `empty` because nobody had pressed refresh would be reporting the
    refresh schedule rather than the model.
    """
    models = await domain_derivation.derive_all_domains(
        request.app.state.repository, user_id=user_id
    )
    order = {domain: i for i, domain in enumerate(PART_16_DOMAIN_ORDER)}
    models.sort(key=lambda m: order[m.domain])
    return DomainListResponse(domains=[_domain_response(m) for m in models])


@router.get("/domains/projects", response_model=ProjectListResponse)
async def list_projects(user_id: UUID, request: Request) -> ProjectListResponse:
    """The project list derived from `MemoryRecord.project_id`, plus the
    `projects` domain's own state -- see the module docstring on why both."""
    repository = request.app.state.repository
    model = await domain_derivation.derive_one_domain(
        repository, TwinDomain.PROJECTS, user_id=user_id
    )
    projects = await repository.list_project_models(user_id)
    return ProjectListResponse(
        domain=_domain_response(model),
        projects=[_project_response(p) for p in projects],
    )


@router.get("/domains/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID, user_id: UUID, request: Request
) -> ProjectDetailResponse:
    """**AC-6.** The reconstruction for one project.

    404 when no memory has ever carried this `project_id` for this user. Not an
    empty project: a project that does not exist and a project with no activity
    are different answers, and returning zeros for the first would invent one.
    """
    repository = request.app.state.repository
    await domain_derivation.derive_one_domain(repository, TwinDomain.PROJECTS, user_id=user_id)
    project = await repository.get_project_model(user_id, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No memory carrying project_id {project_id} has been observed for this "
                "user. MemoryRecord.project_id is the only project identity in the "
                "system, and nothing has referenced this one."
            ),
        )
    return ProjectDetailResponse(project=_project_response(project))


@router.get("/domains/{domain}", response_model=DomainResponse)
async def get_domain(domain: str, user_id: UUID, request: Request) -> DomainResponse:
    """One domain's current model and the provenance count behind it."""
    model = await domain_derivation.derive_one_domain(
        request.app.state.repository, _parse_domain(domain), user_id=user_id
    )
    return _domain_response(model)


@router.post("/domains/{domain}/refresh", response_model=DomainResponse)
async def refresh_domain(domain: str, user_id: UUID, request: Request) -> DomainResponse:
    """Re-derive one domain from its sources. Explicit and user-triggered.

    "Its sources" means this engine's own accumulated `domain_evidence` rows --
    the only source it legally owns (ADR-004; TDD 4E Sec0.1.5). Refresh therefore
    recomputes a model; it does not fetch new raw data, and it cannot invent any.

    A refresh of a domain with no evidence returns `empty` with its reason, not an
    error: "there is nothing to derive" is a successful answer.
    """
    parsed = _parse_domain(domain)
    model = await domain_derivation.derive_one_domain(
        request.app.state.repository, parsed, user_id=user_id
    )
    if model.state is DomainState.POPULATED and model.evidence_count == 0:  # pragma: no cover
        # Unreachable: `DomainModel`'s own validator raises first. Kept as a
        # belt-and-braces read of the one invariant this whole surface exists to
        # hold, so a future refactor that weakened the validator fails here too.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="derivation produced a populated domain with no evidence",
        )
    return _domain_response(model)

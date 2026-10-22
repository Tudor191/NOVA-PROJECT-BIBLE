"""`/v1/autonomy/*` -- TDD 4D §8.1, and nothing beyond it.

**The boundary against `action-engine`, as §8.1 defines it:**

> `action-engine`'s `POST /v1/action/approvals/{id}/decide` decides **one
> already-created `Action`** inside its own execution pipeline.
> `autonomy-engine`'s `/v1/autonomy/*` governs **whether NOVA may act at all**
> -- levels, policies, permissions, trust, and the suggestions those produce.
> Neither endpoint is reachable from the other's domain, and neither is
> deprecated by this milestone.

**This module creates no route the TDD does not name.** In particular there is
no route that *creates* a suggestion: §8.1's table has none, D-4D-1 removed the
Event Bus origin, and inventing one because it would be convenient is exactly
what this milestone was told not to do. The consequence is disclosed rather
than papered over -- in this release the inbox has no production producer, and
`GET /v1/autonomy/suggestions` returns a healthy empty state saying so.

There is also **no identity-confidence-policy route**: CF-9 stays open and
`action-engine` keeps sole ownership of that policy (D-4D-2, §11).

**Nothing here executes anything.** Approving a suggestion records the user's
decision; `DecisionResultResponse.executed` is `False` and says so explicitly.

**Every change to this engine's authority is logged and counted** *(added
2026-10-16, SAD 15 §9.1 items 9 and 10)*. Setting the level, creating,
updating or deleting a policy, and replacing permission grants each emit one
`autonomy configuration changed` log line carrying the values before and
after, and increment `autonomy_configuration_changes_total`. These are the
changes that can let an action execute without approval (an `AUTO_EXECUTE`
policy at Level 2), so an operator must be able to see when they happened.
This is a log line, **not an audit trail**: nothing is persisted, and who
made the change is not recorded beyond the single trusted user of ADR-025.
A persisted audit of these changes is an open decision (closure matrix
N-02), not something this module claims to provide.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from nova_observability import get_logger

from nova_autonomy_engine.api.schemas import (
    AutonomyOverviewResponse,
    DecideSuggestionRequest,
    DecisionResultResponse,
    GateReportResponse,
    LevelOption,
    LevelResponse,
    PermissionGrantResponse,
    PermissionMatrixResponse,
    PolicyCheckResponse,
    PolicyCreateRequest,
    PolicyResponse,
    PolicyUpdateRequest,
    SetLevelRequest,
    SetPermissionsRequest,
    SuggestionListResponse,
    SuggestionResponse,
    TrustScoreResponse,
)
from nova_autonomy_engine.domain.decision import DecisionRequest, GateReport, evaluate_gates
from nova_autonomy_engine.domain.levels import (
    LevelNotDefinedError,
    LevelNotSelectableError,
    level_name,
    parse_level,
    require_selectable,
)
from nova_autonomy_engine.domain.models import (
    AUTONOMY_LEVEL_NAMES,
    DEFINED_LEVELS,
    PERMISSION_CATEGORY_ORDER,
    SELECTABLE_LEVELS,
    AutonomyLevel,
    DecisionLogEntry,
    DecisionOutcome,
    PermissionGrant,
    Policy,
    PolicyMatch,
    Suggestion,
    SuggestionStatus,
    TrustInputStatus,
)
from nova_autonomy_engine.domain.permissions import matrix_by_category
from nova_autonomy_engine.domain.ports import (
    SuggestionAlreadyDecidedError,
    SuggestionNotFoundError,
)
from nova_autonomy_engine.domain.trust import compute_trust_score
from nova_autonomy_engine.repository.cursor import InvalidCursorError

logger = get_logger("autonomy-engine")

#: The header `api-gateway` forwards (its `domain/envelope.py`; restated, not
#: imported, per ADR-004). The gateway accepts a caller-supplied value and a
#: direct caller sends none, so it ties a line to a request trace and proves
#: nothing about who sent the request.
_CORRELATION_ID_HEADER = "x-correlation-id"

#: The routes that change this engine's authority, by route template.
_CONFIGURATION_ROUTES = {
    "/v1/autonomy/level": "level",
    "/v1/autonomy/policies": "policy",
    "/v1/autonomy/policies/{policy_id}": "policy",
    "/v1/autonomy/permissions": "permissions",
}
_OPERATIONS = {"PUT": "set", "POST": "create", "PATCH": "update", "DELETE": "delete"}


def _context(request: Request) -> dict[str, object]:
    """What a configuration line is about, as far as this engine can know.

    `user_id` is the target, resolved server-side (ADR-025). `actor` is always
    None: `api-gateway` authenticates one shared session token and forwards no
    principal, and a request reaching the engine directly carries none, so
    the engine cannot tell who asked."""
    return {
        "correlation_id": request.headers.get(_CORRELATION_ID_HEADER),
        "user_id": str(request.app.state.settings.primary_user_id),
        "actor": None,
    }


def _configuration_refused(
    request: Request, *, kind: str, status_code: int, reason: object
) -> None:
    logger.warning(
        "autonomy configuration change refused",
        extra={
            "kind": kind,
            "operation": _OPERATIONS[request.method],
            "outcome": "refused",
            "status_code": status_code,
            "reason": reason,
            **_context(request),
        },
    )


class _ConfigurationRoute(APIRoute):
    """Logs a refused write to a configuration route, then lets FastAPI answer
    it exactly as before. A 422 from request validation is raised before the
    handler runs, so the handler alone cannot log it."""

    def get_route_handler(self):  # type: ignore[no-untyped-def]
        handler = super().get_route_handler()
        kind = _CONFIGURATION_ROUTES.get(self.path)
        if kind is None or not self.methods & _OPERATIONS.keys():
            return handler

        async def logged(request: Request):  # type: ignore[no-untyped-def]
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Locations and error types only: the rejected values are the
                # caller's input, not something this line needs to repeat.
                reason = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
                _configuration_refused(request, kind=kind, status_code=422, reason=reason)
                raise
            except HTTPException as exc:
                if 400 <= exc.status_code < 500:
                    _configuration_refused(
                        request, kind=kind, status_code=exc.status_code, reason=exc.detail
                    )
                raise

        return logged


router = APIRouter(prefix="/v1/autonomy", tags=["autonomy"], route_class=_ConfigurationRoute)

_UNCONFIGURED_LEVEL = AutonomyLevel.OBSERVATION_ONLY
"""What an unconfigured instance behaves as. Bible Part 14's Level 0 -- *"NOVA
never acts"* -- so installing 4D changes no existing behaviour until a user
configures something (TDD §19)."""


def _state(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state


def _configuration_changed(
    request: Request, *, kind: str, operation: str, **detail: object
) -> None:
    """One log line and one count for each change to this engine's authority.

    An operational log line, not an audit record: it goes to stdout and is
    not persisted. The `*_before` values come from a read made before the
    write, in a separate statement, so under a concurrent write they may not
    be the value this write replaced."""
    logger.info(
        "autonomy configuration changed",
        extra={
            "kind": kind,
            "operation": operation,
            "outcome": "applied",
            **detail,
            **_context(request),
        },
    )
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        metrics.configuration_changes_total.add(1, {"kind": kind, "operation": operation})


def _policy_snapshot(policy: Policy | None) -> dict[str, object] | None:
    """The fields that decide what a policy permits -- never its free-text name
    alone, which says nothing about its effect."""
    if policy is None:
        return None
    return {
        "effect": policy.effect.value,
        "enabled": policy.enabled,
        "category": policy.match.category.value if policy.match.category else None,
        "min_risk": policy.match.min_risk.value if policy.match.min_risk else None,
        "capability_class": policy.match.capability_class,
    }


def _suggestion_decision(
    request: Request, *, suggestion_id: UUID, decision: str, result: str
) -> None:
    logger.info(
        "suggestion decision",
        extra={
            "suggestion_id": str(suggestion_id),
            "decision": decision,
            "result": result,
            **_context(request),
        },
    )


def _level_options() -> list[LevelOption]:
    """Levels 0-2 only. 3-5 are named in the vocabulary and **not rendered** --
    TDD §12: offering a level with no defined semantics would invite a user to
    ask for one."""
    options: list[LevelOption] = []
    for level in sorted(DEFINED_LEVELS):
        selectable = level in SELECTABLE_LEVELS
        options.append(
            LevelOption(
                level=int(level),
                name=AUTONOMY_LEVEL_NAMES[level],
                selectable=selectable,
                note=None if selectable else "enabled in a later milestone",
            )
        )
    return options


async def _level_response(state, user_id: UUID) -> LevelResponse:  # type: ignore[no-untyped-def]
    setting = await state.repository.get_level(user_id)
    level = setting.level if setting is not None else _UNCONFIGURED_LEVEL
    return LevelResponse(
        level=int(level),
        name=level_name(level),
        updated_at=setting.updated_at if setting is not None else None,
        configured=setting is not None,
        options=_level_options(),
    )


async def _trust_scores(state, user_id: UUID) -> list[TrustScoreResponse]:  # type: ignore[no-untyped-def]
    """One score per category, Bible Part 14: *"a dynamic trust score for every
    category."* The 2D-D input is read **once** and applied per category --
    reading it ten times would be ten identical round trips for one signal."""
    read = await state.trust_source.read(user_id)
    scores: list[TrustScoreResponse] = []
    for category in PERMISSION_CATEGORY_ORDER:
        score = compute_trust_score(
            user_id=user_id,
            category=category,
            conversational=read.snapshot,
            status=read.status,
            detail=read.detail,
        )
        scores.append(
            TrustScoreResponse(
                category=category,
                score=score.score,
                status=score.input_status,
                evidence_count=score.evidence_count,
                detail=score.detail,
            )
        )
    return scores


async def _permission_matrix(state, user_id: UUID) -> PermissionMatrixResponse:  # type: ignore[no-untyped-def]
    grants = await state.repository.list_permission_grants(user_id)
    matrix = matrix_by_category(grants)
    return PermissionMatrixResponse(
        categories=[
            PermissionGrantResponse(
                category=category,
                max_risk=grant.max_risk if grant is not None else None,
                requires_approval_above=(
                    grant.requires_approval_above if grant is not None else None
                ),
                granted=grant is not None,
                updated_at=grant.updated_at if grant is not None else None,
            )
            for category, grant in matrix.items()
        ]
    )


def _policy_response(policy: Policy) -> PolicyResponse:
    return PolicyResponse(
        id=policy.id,
        name=policy.name,
        effect=policy.effect,
        match_category=policy.match.category,
        match_min_risk=policy.match.min_risk,
        match_capability_class=policy.match.capability_class,
        enabled=policy.enabled,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _gate_response(report: GateReport) -> GateReportResponse:
    return GateReportResponse(
        denied=report.denied,
        gate=report.gate,
        reason=report.reason,
        requires_approval=report.requires_approval,
        policy_checks=[
            PolicyCheckResponse(
                policy_id=check.policy_id,
                name=check.name,
                effect=check.effect,
                matched=check.matched,
            )
            for check in report.policy_checks
        ],
    )


def _evaluate(suggestion: Suggestion, policies, grants) -> GateReport:  # type: ignore[no-untyped-def]
    return evaluate_gates(
        DecisionRequest(
            user_id=suggestion.user_id,
            category=suggestion.category,
            risk=suggestion.risk,
            title=suggestion.title,
            detail=suggestion.detail,
        ),
        policies=policies,
        grants=grants,
    )


def _suggestion_response(suggestion: Suggestion, gates: GateReport) -> SuggestionResponse:
    return SuggestionResponse(
        id=suggestion.id,
        category=suggestion.category,
        risk=suggestion.risk,
        title=suggestion.title,
        detail=suggestion.detail,
        status=suggestion.status,
        created_at=suggestion.created_at,
        decided_at=suggestion.decided_at,
        gates=_gate_response(gates),
    )


# --- Overview ---------------------------------------------------------------
@router.get("", response_model=AutonomyOverviewResponse)
async def overview(request: Request) -> AutonomyOverviewResponse:
    state = _state(request)
    user_id = state.settings.primary_user_id
    trust = await _trust_scores(state, user_id)
    degraded = sorted(
        {
            "conversational_trust"
            for score in trust
            if score.status is TrustInputStatus.UNAVAILABLE
        }
    )
    return AutonomyOverviewResponse(
        level=await _level_response(state, user_id),
        trust=trust,
        permissions=await _permission_matrix(state, user_id),
        proposed_count=await state.repository.count_suggestions(
            user_id, status=SuggestionStatus.PROPOSED
        ),
        policy_count=len(await state.repository.list_policies(user_id)),
        degraded=degraded,
    )


# --- Level ------------------------------------------------------------------
@router.get("/level", response_model=LevelResponse)
async def get_level(request: Request) -> LevelResponse:
    state = _state(request)
    return await _level_response(state, state.settings.primary_user_id)


@router.put("/level", response_model=LevelResponse)
async def set_level(body: SetLevelRequest, request: Request) -> LevelResponse:
    """**Rejects Levels 2-5 with a 422 naming the reason** (TDD §8.1, §13).
    Never silently clamped: a user who asks for Level 2 must be told it exists
    and is not yet enabled, not quietly given Level 1."""
    state = _state(request)
    try:
        level = require_selectable(parse_level(body.level))
    except (LevelNotDefinedError, LevelNotSelectableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    previous = await state.repository.get_level(state.settings.primary_user_id)
    await state.repository.set_level(state.settings.primary_user_id, level)
    _configuration_changed(
        request,
        kind="level",
        operation="set",
        level_before=int(previous.level) if previous is not None else None,
        level_after=int(level),
    )
    return await _level_response(state, state.settings.primary_user_id)


# --- Policies ---------------------------------------------------------------
@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(request: Request) -> list[PolicyResponse]:
    state = _state(request)
    policies = await state.repository.list_policies(state.settings.primary_user_id)
    return [_policy_response(policy) for policy in policies]


@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(body: PolicyCreateRequest, request: Request) -> PolicyResponse:
    state = _state(request)
    policy = Policy(
        user_id=state.settings.primary_user_id,
        name=body.name,
        effect=body.effect,
        match=PolicyMatch(
            category=body.match_category,
            min_risk=body.match_min_risk,
            capability_class=body.match_capability_class,
        ),
        enabled=body.enabled,
    )
    created = await state.repository.create_policy(policy)
    _configuration_changed(
        request,
        kind="policy",
        operation="create",
        policy_id=str(created.id),
        policy_before=None,
        policy_after=_policy_snapshot(created),
    )
    return _policy_response(created)


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID, body: PolicyUpdateRequest, request: Request
) -> PolicyResponse:
    state = _state(request)
    user_id = state.settings.primary_user_id
    existing = await state.repository.get_policy(user_id, policy_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such policy")
    merged = existing.model_copy(
        update={
            "name": body.name if body.name is not None else existing.name,
            "effect": body.effect if body.effect is not None else existing.effect,
            "match": PolicyMatch(
                category=(
                    body.match_category
                    if body.match_category is not None
                    else existing.match.category
                ),
                min_risk=(
                    body.match_min_risk
                    if body.match_min_risk is not None
                    else existing.match.min_risk
                ),
                capability_class=(
                    body.match_capability_class
                    if body.match_capability_class is not None
                    else existing.match.capability_class
                ),
            ),
            "enabled": body.enabled if body.enabled is not None else existing.enabled,
        }
    )
    updated = await state.repository.replace_policy(merged)
    if updated is None:  # pragma: no cover - only reachable on a concurrent delete
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such policy")
    _configuration_changed(
        request,
        kind="policy",
        operation="update",
        policy_id=str(policy_id),
        policy_before=_policy_snapshot(existing),
        policy_after=_policy_snapshot(updated),
    )
    return _policy_response(updated)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: UUID, request: Request) -> None:
    state = _state(request)
    user_id = state.settings.primary_user_id
    # Read first only so the log line can say what was removed: deleting a
    # `deny` policy widens authority as surely as creating an `auto_execute`
    # one, and a bare id would not show which happened.
    existing = await state.repository.get_policy(user_id, policy_id)
    deleted = await state.repository.delete_policy(user_id, policy_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such policy")
    _configuration_changed(
        request,
        kind="policy",
        operation="delete",
        policy_id=str(policy_id),
        policy_before=_policy_snapshot(existing),
        policy_after=None,
    )


# --- Permission matrix ------------------------------------------------------
@router.get("/permissions", response_model=PermissionMatrixResponse)
async def get_permissions(request: Request) -> PermissionMatrixResponse:
    state = _state(request)
    return await _permission_matrix(state, state.settings.primary_user_id)


@router.put("/permissions", response_model=PermissionMatrixResponse)
async def set_permissions(
    body: SetPermissionsRequest, request: Request
) -> PermissionMatrixResponse:
    """Upserts **only the categories named**. A category left out of the body
    keeps the row it had -- it is never reset to a permissive default, which is
    how a partial write would widen authority."""
    state = _state(request)
    user_id = state.settings.primary_user_id
    existing_grants = await state.repository.list_permission_grants(user_id)
    before = {grant.category.value: grant for grant in existing_grants}
    await state.repository.upsert_permission_grants(
        user_id,
        [
            PermissionGrant(
                user_id=user_id,
                category=grant.category,
                max_risk=grant.max_risk,
                requires_approval_above=grant.requires_approval_above,
            )
            for grant in body.grants
        ],
    )

    def _grant(grant: object | None) -> dict[str, object] | None:
        if grant is None:
            return None
        max_risk = getattr(grant, "max_risk", None)
        above = getattr(grant, "requires_approval_above", None)
        return {
            "max_risk": max_risk.value if max_risk is not None else None,
            "requires_approval_above": above.value if above is not None else None,
        }

    _configuration_changed(
        request,
        kind="permissions",
        operation="set",
        changes={
            grant.category.value: {
                "before": _grant(before.get(grant.category.value)),
                "after": _grant(grant),
            }
            for grant in body.grants
        },
    )
    return await _permission_matrix(state, user_id)


# --- Suggestions ------------------------------------------------------------
@router.get("/suggestions", response_model=SuggestionListResponse)
async def list_suggestions(
    request: Request,
    suggestion_status: Annotated[SuggestionStatus | None, Query(alias="status")] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SuggestionListResponse:
    """Keyset paginated. There is no `offset` parameter, and a cursor this
    service did not mint is a 422 rather than a silent restart."""
    state = _state(request)
    user_id = state.settings.primary_user_id
    try:
        page = await state.repository.list_suggestions(
            user_id, status=suggestion_status, limit=limit, cursor=cursor
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    policies = await state.repository.list_policies(user_id)
    grants = await state.repository.list_permission_grants(user_id)
    return SuggestionListResponse(
        items=[
            _suggestion_response(suggestion, _evaluate(suggestion, policies, grants))
            for suggestion in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.post("/suggestions/{suggestion_id}/decide", response_model=DecisionResultResponse)
async def decide_suggestion(
    suggestion_id: UUID, body: DecideSuggestionRequest, request: Request
) -> DecisionResultResponse:
    """**The AC-5 control.** The only transition out of `proposed`.

    Three refusals, each with its own status:

    * unknown id -> **404** (TDD §13);
    * already decided -> **409**, the first decision stands (TDD §13);
    * approving something a gate now denies -> **409**, and the suggestion
      stays `proposed`. A policy is *"absolute unless modified by the user"*
      (Bible Part 14), so it must hold against an approval authored before it.
      Rejecting is always permitted -- a denial can always be acknowledged.

    **Every attempt is recorded, including the refused ones.** TDD §13: *"The
    decision log is append-only and records both attempts."* A refusal that
    left no trace would make the log a record of successes rather than of
    decisions.

    **Nothing is executed.** The response says so in a field rather than
    leaving it to be inferred from an absence.
    """
    state = _state(request)
    user_id = state.settings.primary_user_id

    suggestion = await state.repository.get_suggestion(user_id, suggestion_id)
    if suggestion is None:
        _suggestion_decision(
            request, suggestion_id=suggestion_id, decision=body.decision, result="not_found"
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such suggestion")

    policies = await state.repository.list_policies(user_id)
    grants = await state.repository.list_permission_grants(user_id)
    gates = _evaluate(suggestion, policies, grants)

    setting = await state.repository.get_level(user_id)
    level = setting.level if setting is not None else _UNCONFIGURED_LEVEL
    approving = body.decision == "approve"

    def _entry(outcome: DecisionOutcome, reason: str) -> DecisionLogEntry:
        return DecisionLogEntry(
            id=uuid4(),
            subject_id=suggestion.id,
            autonomy_level=level,
            risk=suggestion.risk,
            confidence=0.0,
            policy_checks=gates.policy_checks,
            outcome=outcome,
            reason=reason,
        )

    # Already decided: refuse before the gates are allowed to reinterpret a
    # settled decision, and record the attempt. The repository's conditional
    # UPDATE below is still the race-safe backstop -- this check is for the
    # clearer message, not for correctness.
    if suggestion.status is not SuggestionStatus.PROPOSED:
        _suggestion_decision(
            request,
            suggestion_id=suggestion_id,
            decision=body.decision,
            result="refused_already_decided",
        )
        await state.repository.append_decision_log(
            _entry(
                DecisionOutcome.DENY,
                f"refused: already {suggestion.status.value}; the first decision stands",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"suggestion {suggestion_id} was already decided "
                f"({suggestion.status.value}); the first decision stands"
            ),
        )

    if approving and gates.denied:
        _suggestion_decision(
            request,
            suggestion_id=suggestion_id,
            decision=body.decision,
            result=f"refused_{gates.gate}_gate",
        )
        await state.repository.append_decision_log(
            _entry(
                DecisionOutcome.DENY,
                f"refused: the {gates.gate} gate denies this suggestion: {gates.reason}",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"this suggestion is denied by the {gates.gate} gate: {gates.reason}",
        )

    outcome = DecisionOutcome.PROPOSE if approving else DecisionOutcome.DENY
    entry = _entry(
        outcome,
        "approved by explicit user decision; nothing executed"
        if approving
        else "rejected by explicit user decision",
    )

    try:
        decided = await state.repository.decide_suggestion(
            user_id,
            suggestion_id,
            status=SuggestionStatus.APPROVED if approving else SuggestionStatus.REJECTED,
            log_entry=entry,
        )
    except SuggestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="no such suggestion"
        ) from exc
    except SuggestionAlreadyDecidedError as exc:
        _suggestion_decision(
            request,
            suggestion_id=suggestion_id,
            decision=body.decision,
            result="refused_already_decided",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    _suggestion_decision(
        request, suggestion_id=suggestion_id, decision=body.decision, result=decided.status.value
    )
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        metrics.decisions_total.add(1, {"source": "suggestion_inbox", "outcome": outcome.value})
    return DecisionResultResponse(
        suggestion=_suggestion_response(decided, gates), outcome=outcome, executed=False
    )

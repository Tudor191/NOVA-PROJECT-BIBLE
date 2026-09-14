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
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status

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

router = APIRouter(prefix="/v1/autonomy", tags=["autonomy"])

_UNCONFIGURED_LEVEL = AutonomyLevel.OBSERVATION_ONLY
"""What an unconfigured instance behaves as. Bible Part 14's Level 0 -- *"NOVA
never acts"* -- so installing 4D changes no existing behaviour until a user
configures something (TDD §19)."""


def _state(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state


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
    await state.repository.set_level(state.settings.primary_user_id, level)
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
    return _policy_response(await state.repository.create_policy(policy))


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
    return _policy_response(updated)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: UUID, request: Request) -> None:
    state = _state(request)
    deleted = await state.repository.delete_policy(state.settings.primary_user_id, policy_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such policy")


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return DecisionResultResponse(
        suggestion=_suggestion_response(decided, gates), outcome=outcome, executed=False
    )

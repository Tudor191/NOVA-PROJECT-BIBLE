"""`/v1/action/identity-confidence-policy` -- **CF-9's write surface**
(Phase 4F.4; TDD 4F §5.2, TDD 4F.4 §6, §16.2).

ADR-032 decision point 2 requires *"a configurable identity-confidence
threshold per privileged capability (or per capability class), never a single
hardcoded system-wide threshold"*. `action-engine` has **enforced** that gate at
pipeline stage 3 since Phase 3D and has **modelled** the policy since then too
-- but nothing in the repository could ever *create* the row it reads, so the
threshold was 1.0 at every risk tier forever and every action was denied. This
module is the missing write path, and nothing else.

**Risk tier is the capability class** (**D-4F4-1**). The existing
risk-tier-keyed schema is authoritative; no capability id, no capability table
and no second keying dimension is introduced.

**A single resource, not a collection** (**D-4F4-2**). The table has `user_id`
as its PRIMARY KEY -- one row per user -- so a collection shape would invent an
identifier the schema does not have and imply a multiplicity it cannot store.

**What this module does not touch.** Stage 3's evaluation is not modified: this
supplies rows, it does not change how they are read or compared. There is no new
table, no migration, no ORM class, no Event Bus subject and no `api-gateway`
change -- `/v1/action` already forwards this subtree.

*(Added 2026-10-16, SAD 15 §9.1 item 9.)* **Every change is logged** with the
map before and after, and a write that lowers any tier's threshold -- a weaker
gate -- is logged at `WARNING`. This is a log line, **not an audit trail**:
D-4F4-3 (no audit persistence, no Event Bus subject) stands, and L-15 stays
open for the decision on a persisted audit.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from nova_contracts.events.planning import RiskLevel
from nova_observability import get_logger
from pydantic import BaseModel, Field, field_validator

logger = get_logger("action-engine.identity-confidence-policy")

#: The header `api-gateway` forwards (its `domain/envelope.py`; restated, not
#: imported, per ADR-004). The gateway accepts a caller-supplied value and a
#: direct caller sends none, so it ties a line to a request trace and proves
#: nothing about who sent the request.
_CORRELATION_ID_HEADER = "x-correlation-id"

#: A correlation id this engine will log as written: a UUID, as `api-gateway`
#: mints, or another short token of these characters. Anything else -- too
#: long, a line break, a quote, a control or non-ASCII character -- is logged as
#: `"<invalid>"`, never as the caller's text.
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_INVALID = "<invalid>"

#: A refused request's validation errors beyond this many are counted, not listed.
_MAX_REASONS = 10

#: A refusal is named by its status, never its message.
_STATUS_REASONS = {404: "not_found", 409: "conflict"}


def _context(request: Request) -> dict[str, object]:
    """What a policy line is about, as far as this engine can know.

    `user_id` is the target, resolved server-side (ADR-025). `actor` is always
    None: `api-gateway` authenticates one shared session token and forwards no
    principal, and a request reaching the engine directly carries none, so
    the engine cannot tell who asked."""
    correlation_id = request.headers.get(_CORRELATION_ID_HEADER)
    if correlation_id is not None and _TOKEN.fullmatch(correlation_id) is None:
        correlation_id = _INVALID
    return {
        "correlation_id": correlation_id,
        "user_id": str(_identity(request)),
        "actor": None,
    }


def _log_refusal(request: Request, *, status_code: int, reason: object) -> None:
    logger.warning(
        "identity-confidence policy change refused",
        extra={
            "operation": request.method.lower(),
            "outcome": "refused",
            "status_code": status_code,
            "reason": reason,
            **_context(request),
        },
    )


class _PolicyWriteRoute(APIRoute):
    """Logs a refused `PUT` or `DELETE`, then lets FastAPI answer it exactly as
    before. The 0.75 ceiling and the tier check are request validation, which
    answers 422 before the handler runs, so the handler alone cannot log it."""

    def get_route_handler(self):  # type: ignore[no-untyped-def]
        handler = super().get_route_handler()
        if not self.methods & {"PUT", "DELETE"}:
            return handler

        async def logged(request: Request):  # type: ignore[no-untyped-def]
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Locations and error types only, never the rejected values,
                # and at most `_MAX_REASONS` of them; a risk-tier key is the
                # caller's text, so it is not logged.
                errors = exc.errors()
                reason: list[dict[str, object]] = [
                    {
                        "loc": [
                            part if part in _KNOWN_LOCATIONS else "<unrecognized>"
                            for part in e["loc"]
                        ],
                        "type": e["type"],
                    }
                    for e in errors[:_MAX_REASONS]
                ]
                if len(errors) > _MAX_REASONS:
                    reason.append({"more": len(errors) - _MAX_REASONS})
                _log_refusal(request, status_code=422, reason=reason)
                raise
            except HTTPException as exc:
                if 400 <= exc.status_code < 500:
                    _log_refusal(
                        request,
                        status_code=exc.status_code,
                        reason=_STATUS_REASONS.get(exc.status_code, f"http_{exc.status_code}"),
                    )
                raise

        return logged


router = APIRouter(
    prefix="/v1/action", tags=["identity-confidence-policy"], route_class=_PolicyWriteRoute
)

_FAIL_CLOSED = 1.0
"""What stage 3 uses for a tier absent from the map, or when no row exists."""

_ROUTE = "/identity-confidence-policy"

MAX_CONFIGURABLE_CONFIDENCE = 0.75
"""The highest threshold an operator may *write* (**D-4F4-4**, TDD 4F.4 §16.5).

It mirrors `perception-engine`'s `SINGLE_SIGNAL_CONFIDENCE_CEILING`: a real
single-signal identity cannot exceed it, so a threshold above it is
unsatisfiable by any signal that exists today. Accepting one would store a
policy that looks configured and can never pass.

**This removes no security capability**, because strictness is expressed by
*omission*: stage 3 uses 1.0 for any risk tier absent from the map, so maximum
strictness for a tier means leaving it out, and maximum strictness everywhere
means no row at all.

**Declared here rather than imported.** `perception-engine` owns that constant
and ADR-004 forbids one engine importing another's internals. A drift guard in
`tools/tests/` reads both as source text and fails if they diverge -- which is
also what will force the conversation if fusion (L-11) ever raises achievable
confidence above 0.75.
"""

_VALID_RISK_TIERS = frozenset(level.value for level in RiskLevel)


class IdentityConfidencePolicyRequest(BaseModel):
    """What an operator may set.

    **There is no `user_id` field, deliberately.** Identity is resolved
    server-side from `Settings.primary_user_id` (ADR-025), so a caller-supplied
    identity is *unrepresentable* rather than merely rejected -- the discipline
    4E established and 4F.2/4F.3 carried forward.
    """

    model_config = {"extra": "ignore"}
    """A body carrying `user_id` is accepted and the field ignored, exactly as
    4F.2's workspace intake behaves. The stored row takes its identity from the
    server either way; rejecting the request would tell a prober that the field
    is interesting."""

    minimum_confidence_by_risk: dict[str, float] = Field(
        description="Keyed by RiskLevel value; each value in [0.0, 0.75]."
    )

    @field_validator("minimum_confidence_by_risk")
    @classmethod
    def _validate(cls, value: dict[str, float]) -> dict[str, float]:
        for tier, threshold in value.items():
            if tier not in _VALID_RISK_TIERS:
                # An unrecognised key is silently ignored by stage 3's
                # `risk.value in policy...` lookup, so storing one would look
                # configured while changing nothing -- the quietest possible
                # way to believe a gate is set when it is not.
                raise ValueError(
                    f"unknown risk tier {tier!r}; expected one of "
                    f"{sorted(_VALID_RISK_TIERS)}"
                )
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(
                    f"threshold for {tier!r} must be between 0.0 and 1.0, got {threshold}"
                )
            if threshold > MAX_CONFIGURABLE_CONFIDENCE:
                raise ValueError(
                    f"threshold for {tier!r} is {threshold}, above the maximum "
                    f"achievable identity confidence {MAX_CONFIGURABLE_CONFIDENCE}. "
                    "A threshold no signal can reach would never admit an action; "
                    "omit the tier instead, which leaves it at the fail-closed 1.0."
                )
        return value


#: The only names a refused request's error location may log as written.
_KNOWN_LOCATIONS = frozenset(
    {"body", "query", "path", *IdentityConfidencePolicyRequest.model_fields}
)


class IdentityConfidencePolicyResponse(BaseModel):
    user_id: UUID
    """Echoed from the **server's own** resolution. Never accepted from a
    caller; present so an operator can confirm which identity they configured."""

    minimum_confidence_by_risk: dict[str, float]


def _identity(request: Request) -> UUID:
    """The one source of identity for this surface (ADR-025)."""
    user_id: UUID = request.app.state.settings.primary_user_id
    return user_id


def _loosened(before: dict[str, float] | None, after: dict[str, float] | None) -> list[str]:
    """Tiers whose effective threshold went down. An absent tier, or no row at
    all, is the fail-closed 1.0, so adding a tier always loosens it."""
    old = before or {}
    new = after or {}
    return sorted(
        tier
        for tier in _VALID_RISK_TIERS
        if new.get(tier, _FAIL_CLOSED) < old.get(tier, _FAIL_CLOSED)
    )


def _log_change(
    request: Request,
    *,
    operation: str,
    before: dict[str, float] | None,
    after: dict[str, float] | None,
) -> None:
    """An operational log line, not an audit record: stdout only, nothing
    persisted (D-4F4-3, L-15). `before` is read in a separate statement
    before the write, so under a concurrent write it may not be the map this
    write replaced."""
    loosened = _loosened(before, after)
    logger.log(
        logging.WARNING if loosened else logging.INFO,
        "identity-confidence policy changed",
        extra={
            "operation": operation,
            "before": before,
            "after": after,
            "loosened_tiers": loosened,
            "outcome": "applied",
            **_context(request),
        },
    )


@router.get(_ROUTE, response_model=IdentityConfidencePolicyResponse)
async def get_identity_confidence_policy(request: Request) -> IdentityConfidencePolicyResponse:
    """The deployment's own policy, or **404** when none is configured.

    **404 rather than an empty body.** "No policy" and "a policy that happens to
    be empty" are different security states -- the first means threshold 1.0 at
    every tier -- and synthesizing an empty response would render the first as
    the second.
    """
    user_id = _identity(request)
    policy = await request.app.state.repository.find_identity_confidence_policy(user_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no identity-confidence policy is configured",
        )
    return IdentityConfidencePolicyResponse(
        user_id=policy.user_id,
        minimum_confidence_by_risk=policy.minimum_confidence_by_risk,
    )


@router.put(_ROUTE, response_model=IdentityConfidencePolicyResponse)
async def put_identity_confidence_policy(
    body: IdentityConfidencePolicyRequest, request: Request
) -> IdentityConfidencePolicyResponse:
    """Idempotent upsert of the whole map.

    **Replace, not merge**: the stored map is the complete configuration, and a
    merge would make removing a tier impossible -- which is how an operator
    returns that tier to the fail-closed 1.0 default.
    """
    from nova_action_engine.domain.models import IdentityConfidencePolicy

    user_id = _identity(request)
    repository = request.app.state.repository
    previous = await repository.find_identity_confidence_policy(user_id)
    stored = await repository.upsert_identity_confidence_policy(
        IdentityConfidencePolicy(
            user_id=user_id,
            minimum_confidence_by_risk=body.minimum_confidence_by_risk,
        )
    )
    _log_change(
        request,
        operation="create" if previous is None else "replace",
        before=previous.minimum_confidence_by_risk if previous is not None else None,
        after=stored.minimum_confidence_by_risk,
    )
    return IdentityConfidencePolicyResponse(
        user_id=stored.user_id,
        minimum_confidence_by_risk=stored.minimum_confidence_by_risk,
    )


@router.delete(_ROUTE, status_code=status.HTTP_204_NO_CONTENT)
async def delete_identity_confidence_policy(request: Request) -> None:
    """Remove the row, restoring **fail-closed at every risk tier**.

    404 when there was nothing to delete, for the same reason `GET` 404s: the
    caller asked about a policy that does not exist. Either way the engine ends
    fail-closed, which is why this can never be the dangerous direction.
    """
    user_id = _identity(request)
    repository = request.app.state.repository
    previous = await repository.find_identity_confidence_policy(user_id)
    deleted = await repository.delete_identity_confidence_policy(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no identity-confidence policy is configured",
        )
    _log_change(
        request,
        operation="delete",
        before=previous.minimum_confidence_by_risk if previous is not None else None,
        after=None,
    )

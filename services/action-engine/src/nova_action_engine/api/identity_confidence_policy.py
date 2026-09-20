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
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from nova_contracts.events.planning import RiskLevel
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/v1/action", tags=["identity-confidence-policy"])

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


class IdentityConfidencePolicyResponse(BaseModel):
    user_id: UUID
    """Echoed from the **server's own** resolution. Never accepted from a
    caller; present so an operator can confirm which identity they configured."""

    minimum_confidence_by_risk: dict[str, float]


def _identity(request: Request) -> UUID:
    """The one source of identity for this surface (ADR-025)."""
    user_id: UUID = request.app.state.settings.primary_user_id
    return user_id


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
    stored = await request.app.state.repository.upsert_identity_confidence_policy(
        IdentityConfidencePolicy(
            user_id=user_id,
            minimum_confidence_by_risk=body.minimum_confidence_by_risk,
        )
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
    deleted = await request.app.state.repository.delete_identity_confidence_policy(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no identity-confidence policy is configured",
        )

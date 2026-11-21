"""Records one proposed suggestion so the browser has an AC-5 decision to make.

**Why this exists, stated plainly rather than hidden.** AC-5 requires that *"an
autonomous suggestion at Autonomy Level 1 is proposed, not executed, is visible
in the Autonomy panel, and executing it requires explicit user approval"*,
exercised from the browser. The browser's half -- seeing the proposal, seeing
that nothing ran, and approving it explicitly -- is what the Autonomy panel
does, through `api-gateway` like everything else.

*Producing* a suggestion is the half no shipped component performs.
`autonomy-engine`'s decision pipeline builds one, but nothing calls it in
production: ratified decision **D-4D-1** removed the Event Bus origin (4D claims
no `autonomy.*` subject), and TDD 4D §8.1's endpoint table defines no route that
creates one. Adding such a route for the convenience of this test would be
inventing production surface to make a test pass, which is exactly what this
milestone was told not to do. So this script stands in for the producer a later
milestone will build.

**It stands in for the producer, not for the engine.** It runs
`autonomy_engine.domain.decision.decide` -- the real pipeline, with the real
Policy, Permission and Trust gates in their binding order -- and persists the
result through the real `PostgresAutonomyRepository`, so the suggestion and its
decision-log row are written in the one transaction TDD §9 requires. Nothing
here writes SQL of its own, and nothing bypasses a gate.

**What it does not prove**, so the Gate Review can say so without hedging: that
NOVA proposes on its own initiative. 4D builds the decision surface, not the
initiative surface (TDD §1.1), and no milestone has yet built a producer.
Everything downstream of the proposal -- the panel, the gates it displays, the
explicit approval, and the fact that approval executes nothing -- is real.

Usage:

    uv run python tools/e2e_seed_autonomy_suggestion.py

Prints the suggestion id on stdout so the caller can hand it to Playwright.
Exits non-zero, with the reason on stderr, if the pipeline did not propose --
which is itself a real answer (a denied request is not a bug), and the caller
treats it the way the approval driver treats a denied Action: the spec skips
itself rather than failing for something outside its scope.
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID

from nova_autonomy_engine.config import Settings
from nova_autonomy_engine.domain.decision import DecisionRequest, decide
from nova_autonomy_engine.domain.models import (
    AutonomyLevel,
    DecisionOutcome,
    PermissionCategory,
    PermissionGrant,
    RiskLevel,
    TrustInputStatus,
)
from nova_autonomy_engine.domain.ports import ConversationalTrustRead
from nova_autonomy_engine.repository.postgres_autonomy_repository import (
    PostgresAutonomyRepository,
)
from nova_service_kit import create_engine, create_session_factory

_TITLE = "Archive three stale feature branches"
_DETAIL = (
    "Three branches have had no commits for over 90 days and are merged into the "
    "default branch. Archiving them would tidy the branch list; nothing is deleted."
)
_CATEGORY = PermissionCategory.MODIFY
_RISK = RiskLevel.LOW


class _UnavailableTrust:
    """The shipped adapter's answer, inlined so this driver depends on no
    transport. The trust input is unavailable in this release
    (`clients/conversational_trust.py`), which yields a `None` score -- and a
    `None` score never blocks a proposal, because trust does not gate at
    Levels 0-1."""

    async def read(self, user_id: UUID) -> ConversationalTrustRead:
        del user_id
        return ConversationalTrustRead(
            status=TrustInputStatus.UNAVAILABLE,
            detail="no read surface exists for the 2D-D TrustMetric in this release",
        )


async def _main() -> int:
    settings = Settings()
    user_id = settings.primary_user_id
    engine = create_engine(settings.postgres_dsn)
    repository = PostgresAutonomyRepository(create_session_factory(engine))

    try:
        # Level 1 (Suggestive) is what AC-5 names, and it is selectable.
        await repository.set_level(user_id, AutonomyLevel.SUGGESTIVE)

        # A grant the user could author through the panel. Without it the
        # permission gate denies -- correctly, since an absent grant confers no
        # authority -- and there would be nothing to approve.
        await repository.upsert_permission_grants(
            user_id,
            [
                PermissionGrant(
                    user_id=user_id, category=_CATEGORY, max_risk=RiskLevel.MODERATE
                )
            ],
        )

        result = await decide(
            DecisionRequest(
                user_id=user_id,
                category=_CATEGORY,
                risk=_RISK,
                title=_TITLE,
                detail=_DETAIL,
            ),
            level=AutonomyLevel.SUGGESTIVE,
            policies=await repository.list_policies(user_id),
            grants=await repository.list_permission_grants(user_id),
            trust_source=_UnavailableTrust(),
        )

        if result.outcome is not DecisionOutcome.PROPOSE or result.suggestion is None:
            print(
                f"the pipeline returned {result.outcome.value} rather than propose: "
                f"{result.reason}",
                file=sys.stderr,
            )
            return 1

        # One transaction: the suggestion and its decision-log row together.
        await repository.insert_suggestion(result.suggestion, result.log_entry)
        print(result.suggestion.id)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    os.environ.setdefault(
        "AUTONOMY_ENGINE_POSTGRES_DSN",
        "postgresql+asyncpg://nova:nova_dev_password@localhost:5432/nova",
    )
    raise SystemExit(asyncio.run(_main()))

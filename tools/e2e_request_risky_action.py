"""Requests one Critical-risk Action so the browser has an approval to decide.

**Why this exists.** AC-3 requires that "a risky action is blocked pending
approval and then approved", exercised from the browser. The browser's half of
that -- seeing the pending approval and deciding it -- is what the Approvals
panel does, and it goes through `api-gateway` like everything else. But
*requesting* an Action is not a browser capability and must not become one:
`action.execute` is an Event Bus RPC, and the only component whose
`events/published.py` permits publishing it is `agent-os/kernel`.

`agent-os` has no Dockerfile and no compose service -- Phase 3E's ratified
deferred obligation, discharged by Phase 4C's decision D-5 -- so in the Phase 4B
stack there is no running component that can make the request. This script
stands in for the Kernel for exactly that one call, using the same
`BoundEventBus` bound to the same `PUBLISHABLE_SUBJECTS` the Kernel itself uses,
so the allow-list is enforced here rather than bypassed.

**What it is not.** It is not a second approval system, it does not touch
`action-engine`'s pipeline, and it adds no production surface. It is a test
driver playing the role 4C will give to a real container. What it proves is
therefore bounded and stated plainly in the Gate Review: the approval gate, the
browser's view of it, and the decision path are real; the *requester* is a
stand-in.

Fire-and-forget by design. `action.execute` is request/reply, and
`_run_approval_loop` blocks the responder for up to
`approval_timeout_seconds` (300s) while it waits for a decision -- so this
script deliberately abandons the reply after a short timeout. NATS delivers the
request regardless, and `action-engine` processes it whether or not anyone is
still listening for the answer.

Usage:

    uv run python tools/e2e_request_risky_action.py

Prints the `action_id` on stdout so the caller can hand it to Playwright.
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID, uuid4

from nova_contracts import ActionExecuteRequestPayload
from nova_eventbus_sdk import BoundEventBus, get_event_bus

# The Kernel's own allow-list, not a widened one. If `action.execute` ever
# leaves `agent-os/kernel`'s `PUBLISHABLE_SUBJECTS`, this script must fail
# rather than quietly keep working.
_KERNEL_PUBLISHABLE = frozenset({"action.execute"})

# `classify_risk` maps operation `delete` to `RiskLevel.CRITICAL`
# (`action-engine/domain/risk.py`), which is the only tier
# `_run_approval_loop` gates on. Bible Part 12's own Safety Layers example
# for the critical tier is a filesystem delete, and TDD 3D §14's named
# acceptance scenario is the same one.
_OPERATION = "delete"
_ACTION_TYPE = "filesystem"


async def _main() -> int:
    action_id = uuid4()
    requested_by = UUID(
        os.environ.get("NOVA_PRIMARY_USER_ID", "00000000-0000-4000-8000-000000000001")
    )

    bus = BoundEventBus(
        get_event_bus(),
        engine_name="kernel",
        publishable_subjects=_KERNEL_PUBLISHABLE,
        subscribable_subjects=frozenset(),
    )
    await bus.connect()

    payload = ActionExecuteRequestPayload(
        action_id=action_id,
        action_type=_ACTION_TYPE,
        priority="normal",
        source="e2e-approval-driver",
        requested_by=requested_by,
        execution_target="filesystem",
        parameters={"operation": _OPERATION, "path": "e2e-approval-probe.txt"},
        timeout_seconds=30,
    )

    try:
        # Short timeout on purpose -- see the module docstring. The reply
        # cannot arrive until someone approves, which is the browser's job.
        await bus.request(
            "action.execute",
            payload,
            source_engine="kernel",
            correlation_id=action_id,
            timeout_ms=1500,
        )
    except TimeoutError:
        pass
    finally:
        await bus.close()

    print(action_id)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))

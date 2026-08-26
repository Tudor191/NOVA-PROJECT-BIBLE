"""`ActionPort` -- kernel-mediated access to `action-engine` for an Agent
Package's own `execute()` (TDD 3E §9: `coding-agent` "invokes action-engine
(via `action.execute`, `3D`) using granted `filesystem`/`terminal`/`git`
capabilities to make a scripted code change"). Mirrors `model_gateway.py`'s
own precedent exactly: proposed here, not extracted (doc 12/TDD 3E name the
call, never the in-process port shape an agent instance uses to make it),
and reuses `nova_contracts`' already-existing `ActionExecuteRequestPayload`/
`ActionResultPayload` types directly rather than redefining them.

`agent-os/kernel`'s own `InprocessExecutionBackend` constructs the concrete
adapter behind this Protocol and passes it to a `Handler`'s own constructor
at spawn time, alongside `model_gateway` -- see that module's docstring for
the full constructor convention.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nova_contracts import ActionExecuteRequestPayload, ActionResultPayload

__all__ = ["ActionPort"]


@runtime_checkable
class ActionPort(Protocol):
    async def execute(self, request: ActionExecuteRequestPayload) -> ActionResultPayload: ...

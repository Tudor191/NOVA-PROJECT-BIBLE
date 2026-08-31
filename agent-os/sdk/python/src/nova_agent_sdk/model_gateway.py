"""`ModelGatewayPort` -- kernel-mediated access to `ai-model-orchestration-
engine` for an Agent Package's own `execute()` (TDD 3E §9: `research-agent`
and `documentation-agent` both "call ai-model-orchestration-engine... to
produce a structured finding/documentation content"). Proposed here, not
extracted from doc 12/TDD 3E, which name the *call* but never the mechanism
an in-process agent instance uses to make it -- doc 12 §4's own "an agent
never imports the Event Bus SDK directly... all... communication goes
through `on_message`, dispatched by the kernel" establishes the *principle*
(no direct `nova_eventbus_sdk` import from agent code) but not this specific
port shape. Flagged for Gate Review, the same "propose, disclose, minimal"
discipline already applied throughout Phase 3E.

Mirrors `reasoning-engine`'s own `ModelOrchestrationPort`/
`ModelOrchestrationClient` precedent field-for-field (both wrap
`ai_model.generate.request`/`.reply`, `nova_contracts`' own existing,
unmodified types) -- reused directly rather than redefined, since the RPC
itself is identical regardless of which engine calls it.

`agent-os/kernel`'s own `InprocessExecutionBackend` (`domain/
execution_backend.py`) is what actually constructs the concrete adapter
behind this Protocol and passes it to a `Handler`'s own constructor at spawn
time -- see that module's docstring for the constructor convention this
establishes (`Handler.__init__(self, *, agent_instance_id, model_gateway)`).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nova_contracts import GenerateReplyPayload, GenerateRequestPayload

__all__ = ["ModelGatewayPort"]


@runtime_checkable
class ModelGatewayPort(Protocol):
    async def generate(self, request: GenerateRequestPayload) -> GenerateReplyPayload: ...

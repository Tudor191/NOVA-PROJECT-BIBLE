"""`InprocessExecutionBackend` -- the Phase 3 `AgentExecutionBackend`
implementation (doc 12 §8: "Default for trusted, lightweight, first-party
agents in local-first mode... intentionally the *only* backend at first").

`spawn()` dynamically imports `agents/<manifest's own id>/src/handler.py`
(the same `importlib.util.spec_from_file_location` convention
`agent-os/registry`'s own `domain/pipeline.py::_load_handler_class`
establishes for its Sandbox Test/On Load stages -- duplicated here, not
imported, since ADR-004 forbids importing another engine's internals; both
copies are ~10 lines and intentionally identical) and drives one Handler
instance through its full assigned-task lifecycle synchronously: `on_load`
-> `on_assign` -> `execute` -> `self_validate` -> `on_unload`. See
`domain/models.py::AgentInstanceHandle`'s own docstring for why this is
synchronous rather than a live, pollable instance -- none of the five Phase
3 agents' scripted behaviors (TDD 3E §9) span multiple dispatch cycles.

**Handler construction convention, disclosed.** `agent-os/registry`'s own
install-time On Load smoke test (`domain/pipeline.py`) calls
`handler_class()` with zero arguments -- a hard constraint this backend
must not break, since it is existing, approved, already-shipped code. This
backend instead constructs
`handler_class(agent_instance_id=..., model_gateway=..., action_port=...)`
as **keyword-only, defaulted** arguments (a real Agent Package's own
`Handler.__init__` gives all three a `= None` default, per
`agent-os/sdk/python`'s own generated-stub convention going forward) --
`handler_class()` (bare) still works for Registry's install-time smoke
test, which never calls `execute()` and therefore never touches any of
them; only a Kernel-spawned instance's real `execute()` call needs the one
or two it actually uses populated, and they always are, since this backend
is the only caller that ever supplies them. `action_port`, disclosed
addition (coding-agent slice): every Handler class now accepts it,
including `research-agent`'s own (a one-line, mechanical constructor-only
change, unused by its `execute()`) -- this backend passes the same three
kwargs uniformly to every Handler class it constructs rather than special-
casing per agent category, so extending the constructor convention is the
smallest change that keeps `spawn()` category-agnostic.

**`spawn_and_review()`, disclosed addition (coding-agent slice).** Doc 12
§8's `send(handle, message)` cannot deliver a `PEER_REVIEW_REQUEST` to a
reviewer instance -- `spawn()` already runs the primary instance to
completion and tears it down before returning (see `send()`'s own
`NotImplementedError` below), so there is never a live instance for
*any* agent to `send()` to in Phase 3's synchronous backend, regardless of
category. Rather than keep a spawned instance alive across a second,
unbounded wait for a message that only ever happens once (peer review),
this method constructs a **second**, independent Handler instance for the
reviewer package and drives it through `on_load` -> `on_message(message)`
-> `on_unload` synchronously, returning the reply directly -- symmetric
with `spawn()`'s own synchronous, complete-and-return shape, and reusing
the exact same dynamic-import/constructor convention. The reviewer's own
`on_message()` (doc 12 §10's Agent Mailbox dispatch target, already the
sanctioned entry point for `PEER_REVIEW_REQUEST` traffic) is where a real
reviewer's actual review logic lives -- this method only drives the
transport, never interprets the reply.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

from nova_agent_sdk import (
    ActionPort,
    AgentContext,
    AgentHandler,
    AgentHealth,
    AgentManifest,
    AgentMessage,
    ModelGatewayPort,
)
from nova_contracts import AgentPackageSnapshot, ResourceUsage

from nova_agent_os_kernel.domain.models import AgentInstanceHandle

__all__ = ["InprocessExecutionBackend"]


def _load_handler_class(handler_path: Path) -> type:
    """Dynamically imports `src/handler.py` and returns its `Handler`
    class -- see this module's own docstring for why this duplicates
    `agent-os/registry`'s identical helper rather than importing it."""
    spec = importlib.util.spec_from_file_location("_agent_instance_handler", handler_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load a module spec from {handler_path!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler_class = getattr(module, "Handler", None)
    if handler_class is None:
        raise ImportError(f"{handler_path!r} does not define a top-level 'Handler' class")
    return handler_class


class InprocessExecutionBackend:
    def __init__(
        self,
        *,
        agents_root: Path,
        model_gateway: ModelGatewayPort,
        action_port: ActionPort | None = None,
    ) -> None:
        self._agents_root = agents_root
        self._model_gateway = model_gateway
        self._action_port = action_port

    def next_instance_id(self) -> UUID:
        """Mints the id `spawn()` will use, ahead of the work starting.

        Disclosed addition (TaskNode-lifecycle slice): the Kernel Scheduler
        must persist a `"running"` `agent_instance` row *before* awaiting
        `spawn()`, so that a Kernel killed mid-dispatch leaves the orphan row
        TDD 3E §4's restart reconciliation is specified to re-queue. That
        requires knowing the instance id first. Kept as a separate method
        rather than having the Scheduler generate a `uuid4()` itself, so the
        id remains the backend's to mint -- a `subprocess`/`container`/
        `remote` backend (Phase 4+) may well need it to carry
        backend-specific structure."""
        return uuid4()

    async def spawn(
        self,
        agent: AgentPackageSnapshot,
        context: AgentContext,
        *,
        instance_id: UUID | None = None,
    ) -> AgentInstanceHandle:
        instance_id = instance_id or self.next_instance_id()
        manifest_id = agent.manifest_json["id"]
        handler_path = self._agents_root / manifest_id / "src" / "handler.py"

        try:
            handler_class = _load_handler_class(handler_path)
            handler_instance: AgentHandler = handler_class(
                agent_instance_id=instance_id,
                model_gateway=self._model_gateway,
                action_port=self._action_port,
            )
            manifest = AgentManifest.model_validate(agent.manifest_json)
            await handler_instance.on_load(manifest)
            await handler_instance.on_assign(context.task, context)
            result = await handler_instance.execute()
            validation = await handler_instance.self_validate(result)
            await handler_instance.on_unload()
        except Exception as exc:  # noqa: BLE001 -- recorded on the handle, not re-raised
            return AgentInstanceHandle(instance_id=instance_id, error=str(exc))

        return AgentInstanceHandle(instance_id=instance_id, result=result, validation=validation)

    async def spawn_and_review(
        self, agent: AgentPackageSnapshot, message: AgentMessage
    ) -> AgentMessage | None:
        manifest_id = agent.manifest_json["id"]
        handler_path = self._agents_root / manifest_id / "src" / "handler.py"

        try:
            handler_class = _load_handler_class(handler_path)
            handler_instance: AgentHandler = handler_class(
                agent_instance_id=message.to_instance_id,
                model_gateway=self._model_gateway,
                action_port=self._action_port,
            )
            manifest = AgentManifest.model_validate(agent.manifest_json)
            await handler_instance.on_load(manifest)
            reply = await handler_instance.on_message(message)
            await handler_instance.on_unload()
        except Exception:  # noqa: BLE001 -- an unreachable/broken reviewer is "no reply"
            return None

        return reply

    async def send(self, handle: AgentInstanceHandle, message: AgentMessage) -> None:
        raise NotImplementedError(
            "spawn() drives an instance synchronously through its full assigned-task "
            "lifecycle and returns only once it has already finished (or failed) -- there "
            "is no live instance left to send() a message to by the time a caller could "
            "hold this handle. Deferred until an agent's own execute() needs to span "
            "multiple dispatch cycles (none of the five Phase 3 agents' scripted "
            "behaviors do, TDD 3E §9)."
        )

    async def health(self, handle: AgentInstanceHandle) -> AgentHealth:
        return AgentHealth(
            status="unhealthy" if handle.error is not None else "healthy",
            latency_ms=0.0,
            error_rate=1.0 if handle.error is not None else 0.0,
            resource_usage=ResourceUsage(cpu_percent=0.0, memory_mb=0.0),
        )

    async def terminate(self, handle: AgentInstanceHandle) -> None:
        """A no-op: `spawn()` has already run the instance to completion by
        the time a caller could hold this handle -- there is no live
        background task left to terminate."""

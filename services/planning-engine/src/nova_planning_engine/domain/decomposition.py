"""Objective Decomposition (Bible Part 9; docs/design/phase-3/
05-tdd-3b-planning-engine.md §6.1) -- the domain module that turns a
completed reasoning process into a structurally valid `TaskGraph`.

**Architecture, per the approved research pass**
(`docs/design/phase-3/11-3b-decomposition-architecture-research.md` §6,
§13): LLM-backed decomposition through the same `ModelOrchestrationPort`/
`ai_model.generate.request` channel `reasoning-engine`'s own hypothesis
generation already uses (ADR-020) -- not an invented heuristic, not a
single-node placeholder. This is the one domain module in this engine that
legitimately calls a model; every structural check below it (duplicate
IDs, cycles, dangling dependencies, critical path) stays fully
deterministic, reusing PR #2's existing pure functions unchanged.

**Structured output, not free text.** Unlike `reasoning-engine`'s
hypothesis generation (a flat list of strings, parsed with a numbered-line
regex), a `TaskGraph` is a nested structure with typed fields -- IDs,
dependencies, an effort estimate, a risk level. This module uses the
tool-calling mechanism `nova_contracts.events.ai_model_orchestration`
already defines (`GenerateRequestPayload.tools`/`GenerateReplyPayload.
tool_calls`) and `ai-model-orchestration-engine`'s connectors already
implement, but which had no real caller before this module -- the research
pass's own §6 left this choice open as "a sub-decision for the
implementation PR." A single local, planning-engine-owned tool schema
(`propose_task_graph`), never a `nova_contracts` change.

**No trust extended to the model's own output.** The model may propose
locally-scoped string IDs (never real UUIDs -- models are unreliable at
generating and consistently re-using random UUIDs across one response);
this module mints the real `TaskNode.id` UUIDs itself and resolves
`depends_on` references against its own mapping. Every resulting node
still passes through PR #2's `find_duplicate_ids` / `find_cycle` /
`find_dangling_dependencies` / `compute_critical_path` in that order
before a `TaskGraph` is returned -- "the model produced it" is never
treated as proof of validity.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from nova_contracts import (
    ContextComponentPayload,
    GenerateRequestPayload,
    PrivacyLevel,
    ToolSchemaPayload,
)

from nova_planning_engine.domain.models import Estimate, RiskLevel, TaskGraph, TaskNode
from nova_planning_engine.domain.ports import ModelOrchestrationPort
from nova_planning_engine.domain.task_graph import (
    admit,
    compute_critical_path,
    find_cycle,
    find_dangling_dependencies,
    find_duplicate_ids,
)

__all__ = ["DecompositionError", "build_prompt_context", "decompose", "decompose_node"]

_TOOL_NAME = "propose_task_graph"

_TASK_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "local_id": {
            "type": "string",
            "description": (
                "A short identifier for this task, unique within this response, "
                "used only to express depends_on references below -- not a real "
                "system ID."
            ),
        },
        "objective": {"type": "string"},
        "depends_on": {
            "type": "array",
            "items": {"type": "string"},
            "description": "local_id values of tasks that must complete before this one starts.",
        },
        "assigned_agent_category": {
            "type": ["string", "null"],
            "description": (
                "A short category label for the kind of agent best suited to this "
                "task (e.g. 'coding-agent'), or null if not yet determinable."
            ),
        },
        "effort_hours": {"type": "number", "exclusiveMinimum": 0},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "risk": {"type": "string", "enum": [level.value for level in RiskLevel]},
    },
    "required": ["local_id", "objective", "depends_on", "effort_hours", "confidence", "risk"],
}

_TOOL_SCHEMA = ToolSchemaPayload(
    name=_TOOL_NAME,
    description=(
        "Propose a Work Breakdown Structure: decompose the given objective into a "
        "set of concrete, actionable tasks with dependencies between them."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": _TASK_ITEM_SCHEMA, "minItems": 1}},
        "required": ["tasks"],
    },
)

_INSTRUCTION = (
    "Decompose the objective above into a Work Breakdown Structure: a set of "
    "concrete, actionable tasks with clear dependencies between them, an effort "
    "estimate, a confidence score, and a risk level for each. Call the "
    f"{_TOOL_NAME} tool with the result. Prefer a small number of well-scoped "
    "tasks over an excessively fine-grained breakdown."
)


class DecompositionError(Exception):
    """Raised when the model call fails, returns no structured output, or the
    structured output cannot be validated into a domain-valid `TaskGraph` --
    the event handler routes this into a defined failure outcome, never lets
    it surface as an unhandled exception (mirrors `reasoning-engine`'s own
    `HypothesisGenerationError`). `reason` is a short, stable label for
    observability (metrics/logs), not part of the human-readable message."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def _component(source: str, text: str, *, priority: int) -> ContextComponentPayload:
    return ContextComponentPayload(
        source=source, text=text, token_estimate=len(text) // 4, priority=priority
    )


def build_prompt_context(
    root_objective: str, chosen_description: str | None
) -> list[ContextComponentPayload]:
    """Formats the decomposition input as `ContextComponent`s the same way
    `ai-model-orchestration-engine`'s Prompt Pipeline expects everywhere
    else in this codebase. `chosen_description` is omitted entirely when
    `None` (Part 11: never substituted with unrelated text) -- mirrors
    `reasoning-engine`'s own `prior_nova_utterance` conditional-append
    pattern in `hypothesis_generation.build_prompt_context`."""
    components = [_component("objective", root_objective, priority=10)]
    if chosen_description:
        components.append(_component("chosen_approach", chosen_description, priority=9))
    components.append(_component("instruction", _INSTRUCTION, priority=10))
    return components


def _build_nodes(raw_tasks: list[Any]) -> list[TaskNode]:
    """Resolves the model's local-id-scoped task list into real `TaskNode`s
    with fresh UUIDs, raising `DecompositionError` (never a bare
    `KeyError`/`TypeError`/pydantic `ValidationError`) for any malformed
    entry. This function's own local-id resolution is what `domain/
    task_graph.py`'s structural checks assume already happened -- those run
    separately, immediately after, in `decompose` below."""
    local_id_to_uuid: dict[str, UUID] = {}
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            raise DecompositionError(
                f"malformed task entry (not an object): {raw!r}", reason="malformed_task"
            )
        local_id = raw.get("local_id")
        if not isinstance(local_id, str) or not local_id:
            raise DecompositionError(
                f"malformed task entry (missing local_id): {raw!r}", reason="malformed_task"
            )
        if local_id in local_id_to_uuid:
            raise DecompositionError(
                f"duplicate local task id in model output: {local_id!r}",
                reason="duplicate_local_id",
            )
        local_id_to_uuid[local_id] = uuid4()

    nodes: list[TaskNode] = []
    for raw in raw_tasks:
        local_id = raw["local_id"]
        depends_on_local = raw.get("depends_on", [])
        if not isinstance(depends_on_local, list):
            raise DecompositionError(
                f"malformed depends_on for task {local_id!r}: {depends_on_local!r}",
                reason="malformed_task",
            )
        depends_on: list[UUID] = []
        for dep_local_id in depends_on_local:
            dep_uuid = local_id_to_uuid.get(dep_local_id)
            if dep_uuid is None:
                raise DecompositionError(
                    f"task {local_id!r} depends on unknown local id {dep_local_id!r}",
                    reason="unknown_dependency_reference",
                )
            depends_on.append(dep_uuid)

        try:
            estimate = Estimate(effort_hours=raw["effort_hours"], confidence=raw["confidence"])
            risk = RiskLevel(raw["risk"])
            node = TaskNode(
                id=local_id_to_uuid[local_id],
                objective=raw["objective"],
                depends_on=depends_on,
                assigned_agent_category=raw.get("assigned_agent_category"),
                estimated_effort=estimate,
                risk=risk,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise DecompositionError(
                f"malformed task fields for {local_id!r}: {exc}", reason="malformed_task_fields"
            ) from exc
        nodes.append(node)
    return nodes


async def decompose(
    *,
    root_objective: str,
    chosen_description: str | None,
    model_port: ModelOrchestrationPort,
    requesting_engine: str,
    correlation_id: UUID,
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL,
) -> TaskGraph:
    """Calls `ModelOrchestrationPort.generate` and validates its reply into a
    structurally valid `TaskGraph`. Raises `DecompositionError` for every
    defined failure mode (Part 14): model timeout/error, no structured
    output, malformed task fields, duplicate/dangling/cyclic dependencies --
    never returns a `TaskGraph` that has not passed every one of PR #2's
    structural invariants."""
    components = build_prompt_context(root_objective, chosen_description)

    try:
        reply = await model_port.generate(
            GenerateRequestPayload(
                context=components,
                tools=[_TOOL_SCHEMA],
                task_type="planning_decomposition",
                privacy_hint=privacy_hint,
                requesting_engine=requesting_engine,
                correlation_id=correlation_id,
            )
        )
    except TimeoutError as exc:
        raise DecompositionError(
            f"model orchestration call timed out: {exc}", reason="model_timeout"
        ) from exc

    if reply.finish_reason == "error":
        raise DecompositionError(
            reply.error or "model call returned finish_reason=error", reason="model_error"
        )

    tool_call = next((c for c in reply.tool_calls if c.tool_name == _TOOL_NAME), None)
    if tool_call is None:
        raise DecompositionError(
            f"model did not call {_TOOL_NAME} -- no structured task graph returned",
            reason="no_structured_output",
        )

    raw_tasks = tool_call.arguments.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise DecompositionError("model returned no tasks to decompose", reason="empty_task_list")

    nodes = _build_nodes(raw_tasks)

    # PR #2's structural invariants, checked in order (Part 12) -- each a
    # distinguishable, observable failure reason rather than one opaque
    # "invalid graph" outcome. Unreachable for duplicate_ids given this
    # module's own fresh-UUID-per-local-id construction above; kept
    # explicit anyway, matching Part 12's own enumerated checklist and as
    # defence-in-depth against a future change to `_build_nodes`.
    duplicates = find_duplicate_ids(nodes)
    if duplicates:
        raise DecompositionError(
            f"duplicate task ids in decomposition: {duplicates}", reason="duplicate_ids"
        )
    cycle = find_cycle(nodes)
    if cycle is not None:
        raise DecompositionError(f"cycle detected in decomposition: {cycle}", reason="cycle")
    dangling = find_dangling_dependencies(nodes)
    if dangling:
        raise DecompositionError(
            f"dangling dependencies in decomposition: {dangling}",
            reason="dangling_dependencies",
        )

    critical_path = compute_critical_path(nodes)
    # Admission (TDD 3E §4:140's own definition of `"ready"`): every node
    # `_build_nodes` produced carries `TaskNode`'s default `"pending"`, and
    # `agent-os/kernel`'s Scheduler dispatches only `"ready"` nodes -- so
    # without this step a structurally valid graph is also a permanently
    # undispatchable one. Runs *after* the structural checks above, never
    # before: `dependencies_satisfied` is only meaningful on a graph already
    # known to be duplicate-free, acyclic, and free of dangling references.
    return TaskGraph(
        root_objective=root_objective, nodes=admit(nodes), critical_path=critical_path
    )


async def decompose_node(
    *,
    node: TaskNode,
    model_port: ModelOrchestrationPort,
    requesting_engine: str,
    correlation_id: UUID,
    privacy_hint: PrivacyLevel = PrivacyLevel.INTERNAL,
) -> list[TaskNode]:
    """`planning.decompose.request` (TDD 3B §6.2, doc 12 §11): a Supervisor
    receiving `node` "still too coarse for a single leaf agent" requests
    further decomposition, scoped to that node's own subtree. Reuses
    `decompose()`'s entire model-call/validation pipeline unchanged --
    `node.objective` seeds the same `propose_task_graph` tool call as a
    fresh `root_objective` would, so the identical "no trust extended to
    the model's own output" structural checks apply with no new code path.

    Returns the empty list when the model itself proposes no further
    breakdown (exactly one resulting task, unmodified from `node`'s own
    objective) -- TDD 3B §8's own "already minimal" case; the caller
    (`events/decompose_handler.py`) turns this into
    `PlanningDecomposeReplyPayload(already_minimal=True)`, never a
    silent no-op reply indistinguishable from success."""
    result = await decompose(
        root_objective=node.objective,
        chosen_description=None,
        model_port=model_port,
        requesting_engine=requesting_engine,
        correlation_id=correlation_id,
        privacy_hint=privacy_hint,
    )
    if len(result.nodes) == 1:
        return []
    return result.nodes

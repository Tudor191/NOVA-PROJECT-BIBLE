"""Context Assembly (docs/design/phase-2b/00-reasoning-engine.md §2, §4, §7) --
the "Load memories / Load World Model / Retrieve knowledge" pipeline steps.
Fans out to `MemoryPort`, `WorldModelPort`, `KnowledgePort`,
`PersonalContextPort`, and `GoalsPort` in parallel (never sequentially -- no
step here depends on another's result), assembling one `ContextBundle`.

This is the one place in NOVA whose entire job *is* sourcing context, because
grounding reasoning in what NOVA already knows is this engine's Priority 1
responsibility (ADR-025).
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from nova_reasoning_engine.domain.models import Constraint, ContextBundle, Goal
from nova_reasoning_engine.domain.ports import (
    GoalsPort,
    KnowledgePort,
    MemoryPort,
    PersonalContextPort,
    WorldModelPort,
)

__all__ = ["assemble_context"]


async def assemble_context(
    *,
    user_id: UUID,
    objective_text: str,
    memory_port: MemoryPort,
    knowledge_port: KnowledgePort,
    world_model_port: WorldModelPort,
    personal_context_port: PersonalContextPort,
    goals_port: GoalsPort,
    caller_goals: list[Goal],
    constraints: list[Constraint],
    scope: str | None = None,
) -> ContextBundle:
    """§7's parallel fan-out. `caller_goals` (explicit, on `ReasoningRequest`)
    take precedence over `GoalsPort`'s own result when both are supplied --
    `GoalsPort`'s Phase 2B placeholder implementation returns the same
    caller-supplied goals anyway (§7.1), so this is forward-compatible with a
    real Planning Engine adapter without changing this function's own logic.
    """
    memories, knowledge, world_model, personal_context, ported_goals = await asyncio.gather(
        memory_port.retrieve(user_id=user_id, query=objective_text),
        knowledge_port.retrieve(query=objective_text),
        world_model_port.get_context(user_id=user_id, scope=scope),
        personal_context_port.get_personal_context(user_id=user_id),
        goals_port.current_goals(user_id=user_id, scope=scope),
    )

    return ContextBundle(
        memories=memories,
        knowledge=knowledge,
        world_model=world_model,
        personal_context=personal_context,
        goals=caller_goals or ported_goals,
        constraints=constraints,
    )

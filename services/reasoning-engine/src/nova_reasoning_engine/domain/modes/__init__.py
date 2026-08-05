"""Reasoning Modes (docs/design/phase-2b/00-reasoning-engine.md §6) -- one
strategy module per mode, each configuring which pipeline steps run, how
deep, and with what cost budget. `pipeline.py` dispatches to the selected
mode's `ModeConfig` rather than branching internally on mode throughout the
pipeline.
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import Constraint, Goal, ModeConfig, ReasoningMode
from nova_reasoning_engine.domain.modes import (
    analytical,
    collaborative,
    constraint_based,
    goal_driven,
    long_term_planning,
    multi_step,
    reactive,
    reflective,
    self_evaluation,
    strategic,
)

__all__ = ["CONFIGS", "NotImplementedModeError", "config_for", "resolve_mode_and_level"]

CONFIGS: dict[ReasoningMode, ModeConfig] = {
    ReasoningMode.REACTIVE: reactive.CONFIG,
    ReasoningMode.ANALYTICAL: analytical.CONFIG,
    ReasoningMode.STRATEGIC: strategic.CONFIG,
    ReasoningMode.LONG_TERM_PLANNING: long_term_planning.CONFIG,
    ReasoningMode.GOAL_DRIVEN: goal_driven.CONFIG,
    ReasoningMode.CONSTRAINT_BASED: constraint_based.CONFIG,
    ReasoningMode.MULTI_STEP: multi_step.CONFIG,
    ReasoningMode.REFLECTIVE: reflective.CONFIG,
    ReasoningMode.SELF_EVALUATION: self_evaluation.CONFIG,
    ReasoningMode.COLLABORATIVE: collaborative.CONFIG,
}


class NotImplementedModeError(Exception):
    """Raised for `ReasoningMode.COLLABORATIVE` (§6, §25) -- named and
    designed for, not stubbed with fake per-agent agreement behavior."""


def config_for(mode: ReasoningMode) -> ModeConfig:
    if mode is ReasoningMode.COLLABORATIVE:
        raise NotImplementedModeError(
            "Collaborative mode depends on NAOS (Phase 3+) and is not implemented in Phase 2B."
        )
    return CONFIGS[mode]


def resolve_mode_and_level(
    *,
    reasoning_mode_hint: ReasoningMode | None,
    reasoning_level_hint: int | None,
    goals: list[Goal],
    constraints: list[Constraint],
) -> tuple[ReasoningMode, int]:
    """§4's "Understand intent" pipeline step -- maps a request to a
    `ReasoningMode` and `ReasoningLevel`. A structural heuristic over
    caller-supplied hints, never a model call (the same non-circularity
    discipline the AI Model Orchestration Engine's `estimate_complexity`
    established). Only covers the modes reachable from a fresh objective;
    Reflective, Self-evaluation, and Collaborative are reached through their
    own dedicated entry points (§6), never resolved heuristically here.
    """
    level = reasoning_level_hint or 2

    if reasoning_mode_hint is not None:
        return reasoning_mode_hint, level

    hard_constraints = [c for c in constraints if c.hard]
    if hard_constraints:
        return ReasoningMode.CONSTRAINT_BASED, level
    if level <= 1:
        return ReasoningMode.REACTIVE, level
    if goals and level >= 3:
        return ReasoningMode.GOAL_DRIVEN, level
    if level == 2:
        return ReasoningMode.ANALYTICAL, level
    if level == 3:
        return ReasoningMode.STRATEGIC, level
    return ReasoningMode.MULTI_STEP, level

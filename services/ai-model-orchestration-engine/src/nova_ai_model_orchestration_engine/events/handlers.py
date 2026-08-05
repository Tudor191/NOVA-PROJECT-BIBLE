"""Event Bus subscription handlers -- docs/design/phase-2a/
00-ai-model-orchestration-engine.md §13: "Subscribes: (none in Phase 2A) --
This engine has no upstream producer to react to yet -- Reasoning Engine (2B)
will be its first real caller."

This module is intentionally empty of reactive handlers: it exists so the
convention (every engine has an `events/handlers.py`) holds, ready for
Reasoning Engine's arrival in Phase 2B, not as a placeholder guessing at a
shape that doesn't exist yet. The two subjects this engine *does* serve
(`ai_model.generate.request`, `ai_model.embed.request`) are request/reply RPCs,
not reactive subscriptions -- their handlers live in `main.py`, matching World
Model Engine's `world_model.context.request` precedent.
"""

from __future__ import annotations

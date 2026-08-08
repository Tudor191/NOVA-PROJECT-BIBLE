"""Session-scoped Conversation Memory (docs/design/phase-2d/
04-conversation-intelligence.md Sec0.8/Sec9) -- Bible Part 13's Conversation
Memory list (objective, questions, decisions, preferences, corrections,
feedback), minus `objective` (already its own `ConversationSession` field
since 2D-A). Extends the existing durable `communication.conversation_session`
row rather than a new Redis store (Sec0.8: this data must survive a restart
exactly as the rest of the session does, so ADR-012's ephemeral,
cheap-to-rebuild category does not apply here).

`decisions`/`preferences`/`corrections`/`feedback` are populated only from
`memory_annotations` a content-source engine optionally sets on its own
`communication.intent.deliver.request` call -- this engine stores what it's
told, categorized by the producing engine, never infers or extracts a
category itself (Sec0.1: this engine never generates or classifies
content). `questions` is populated by the Clarification Engine instead
(`domain/clarification.py`), once a pending question is resolved.
"""

from __future__ import annotations

from nova_communication_engine.domain.models import ConversationMemory

__all__ = ["MEMORY_CATEGORIES", "apply_memory_annotations"]

MEMORY_CATEGORIES = frozenset({"decisions", "preferences", "corrections", "feedback"})
"""The four `ConversationMemory` list fields a `memory_annotations` entry
may target -- deliberately excludes `questions`, which only the
Clarification Engine writes (Sec6.2), and `objective`, which is not part of
`ConversationMemory` at all (it is `ConversationSession.objective`,
Sec0.8)."""


def apply_memory_annotations(
    memory: ConversationMemory, *, annotations: list[dict[str, str]] | None
) -> ConversationMemory:
    """Sec9 -- returns a new `ConversationMemory` with each valid
    annotation appended to its named category's list. An annotation naming
    an unrecognized category (not one of `MEMORY_CATEGORIES`) is dropped,
    not raised -- a content-source engine's forward-compatible extension to
    this list should never crash delivery (Doc 22 Principle 3: an
    engine-to-engine contract quirk is not grounds for silence)."""
    if not annotations:
        return memory

    updates: dict[str, list[str]] = {
        category: list(getattr(memory, category)) for category in MEMORY_CATEGORIES
    }
    for annotation in annotations:
        category = annotation.get("category")
        text = annotation.get("text")
        if category in MEMORY_CATEGORIES and text:
            updates[category].append(text)

    return memory.model_copy(update=updates)

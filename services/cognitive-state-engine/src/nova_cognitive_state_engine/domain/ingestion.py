"""From one workspace observation to one Active Thought -- Phase 4F.P,
**A-4FP-1** and **A-4FP-9** (TDD 4F.P §30.2).

Pure: no I/O, no clock, no randomness. `ingestion_orchestration.py` supplies the
clock reading and does the writing; this module only says what the thought
**is**.

**The identity is the observed object's, and only the object's (A-4FP-9).**
`thought_id = uuid5(_INGESTION_NAMESPACE, object_id)`, with `object_id` used
exactly as `perception-engine` published it: the hash of the file's path. So a
re-published envelope, a later observation of the same file and the same file
seen by a second sensor all name **the same** thought, and the insert-if-absent
write makes every one after the first a no-op. The envelope's `event_id` plays
no part. A new file path is a new identity, and a new initiative.

**Every field has one ratified source, and nothing is read from the observation
but `object_id`, `label` and `project_id`.** The proposal and the description
come from the closed authoring table (A-4FP-3); `label` reaches only the
proposal's `title` and the thought's `description`, never `parameters`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid5

from nova_cognitive_state_engine.domain.authoring import AUTHORING_TABLE, WORKSPACE_OBSERVATION
from nova_cognitive_state_engine.domain.models import ActiveThought, AttentionLayer

__all__ = ["thought_for_workspace_observation", "thought_id_for"]

_INGESTION_NAMESPACE = UUID("77980e9a-8808-5af9-8e41-2442669868a1")
"""**Pinned, never computed at import** -- A-4FP-1. Reproducible as
`uuid5(NAMESPACE_DNS, "perception.workspace.observed.ingest.cognitive-state.nova")`,
which `tests/unit/test_ingestion.py` asserts. Changing it would give every
already-ingested object a second identity, and a second initiative."""


def thought_id_for(object_id: str) -> UUID:
    """The thought identity for one observed object. `object_id` is used
    exactly as received: no stripping, no case folding, no re-hashing."""
    return uuid5(_INGESTION_NAMESPACE, object_id)


def thought_for_workspace_observation(
    *,
    object_id: str,
    label: str,
    project_id: UUID | None,
    user_id: UUID,
    now: datetime,
) -> ActiveThought:
    """The thought A-4FP-1's field table describes, value for value.

    `user_id` is this engine's `primary_user_id` (SD-1) -- the caller has
    already refused an observation naming anyone else. `now` is one reading of
    this engine's clock, written to both timestamps."""
    entry = AUTHORING_TABLE[WORKSPACE_OBSERVATION]
    return ActiveThought(
        thought_id=thought_id_for(object_id),
        user_id=user_id,
        description=entry.describe(label=label),
        priority=1,
        confidence=1.0,
        dependencies=(),
        estimated_completion=None,
        related_memories=(),
        related_projects=(project_id,) if project_id is not None else (),
        current_progress=0.0,
        attention_layer=AttentionLayer.ACTIVE,
        created_at=now,
        updated_at=now,
        proposed_action=entry.author(label=label),
    )

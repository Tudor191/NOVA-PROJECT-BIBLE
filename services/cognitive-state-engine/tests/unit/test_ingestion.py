"""From one workspace observation to one Active Thought -- Phase 4F.P, A-4FP-1
and A-4FP-9 (TDD 4F.P §30.2). Pure domain: the identity, and the field table.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import PurePath
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from nova_cognitive_state_engine.domain import ingestion
from nova_cognitive_state_engine.domain.authoring import T1
from nova_cognitive_state_engine.domain.ingestion import (
    thought_for_workspace_observation,
    thought_id_for,
)
from nova_cognitive_state_engine.domain.models import AttentionLayer

PRIMARY = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def _object_id(path: str) -> str:
    """`perception-engine`'s own derivation (`domain/workspace.py`), restated
    here rather than imported (control 7), so the tests exercise the identity
    form that actually arrives."""
    return "ws-" + hashlib.sha256(PurePath(path.strip()).as_posix().encode()).hexdigest()


def _thought(**overrides: object):  # type: ignore[no-untyped-def]
    fields: dict = {
        "object_id": _object_id(f"/workspace/{uuid4()}/notes.md"),
        "label": "notes.md",
        "project_id": None,
        "user_id": PRIMARY,
        "now": NOW,
    }
    fields.update(overrides)
    return thought_for_workspace_observation(**fields)


# --- the identity (A-4FP-1, A-4FP-9) ------------------------------------------------------


def test_the_namespace_is_the_pinned_literal_and_reproducible() -> None:
    assert UUID("77980e9a-8808-5af9-8e41-2442669868a1") == ingestion._INGESTION_NAMESPACE
    assert (
        uuid5(NAMESPACE_DNS, "perception.workspace.observed.ingest.cognitive-state.nova")
        == ingestion._INGESTION_NAMESPACE
    )


def test_the_identity_is_uuid5_of_the_object_id_exactly_as_received() -> None:
    object_id = _object_id("/workspace/nova/README.md")
    assert thought_id_for(object_id) == uuid5(ingestion._INGESTION_NAMESPACE, object_id)


def test_the_same_object_always_names_the_same_thought() -> None:
    object_id = _object_id("/workspace/nova/README.md")
    assert thought_id_for(object_id) == thought_id_for(object_id)
    assert _thought(object_id=object_id).thought_id == _thought(object_id=object_id).thought_id


def test_the_object_id_is_not_normalised() -> None:
    """Used exactly as received: padding or case is a different input, never
    silently folded into an existing identity."""
    object_id = _object_id("/workspace/nova/README.md")
    variants = {object_id, f" {object_id}", object_id.upper(), f"{object_id}\n"}
    assert len({thought_id_for(variant) for variant in variants}) == len(variants)


def test_a_new_file_path_is_a_new_identity() -> None:
    assert thought_id_for(_object_id("/workspace/a.md")) != thought_id_for(
        _object_id("/workspace/b.md")
    )


def test_nothing_but_the_object_id_decides_the_identity() -> None:
    """A-4FP-9: a later observation of the same file with another label,
    project, clock reading -- the fields that change between observations --
    names the same thought."""
    object_id = _object_id("/workspace/nova/README.md")
    first = _thought(object_id=object_id, label="README.md", now=NOW)
    later = _thought(
        object_id=object_id,
        label="renamed.md",
        project_id=uuid4(),
        now=datetime(2026, 9, 30, tzinfo=UTC),
    )
    assert first.thought_id == later.thought_id


# --- the field table (A-4FP-1) ------------------------------------------------------------


def test_every_field_has_its_ratified_source() -> None:
    project = uuid4()
    thought = _thought(label="nova", project_id=project)

    assert thought.user_id == PRIMARY
    assert thought.description == "Activity observed in nova"
    assert thought.priority == 1
    assert thought.confidence == 1.0
    assert thought.current_progress == 0.0
    assert thought.dependencies == ()
    assert thought.related_memories == ()
    assert thought.related_projects == (project,)
    assert thought.estimated_completion is None
    assert thought.attention_layer is AttentionLayer.ACTIVE
    assert thought.created_at == NOW
    assert thought.updated_at == NOW
    assert thought.proposed_action == T1.author(label="nova")


def test_no_project_means_no_related_project() -> None:
    assert _thought(project_id=None).related_projects == ()


def test_the_label_reaches_only_the_description_and_the_title() -> None:
    label = "quarterly-plan.md"
    thought = _thought(label=label)
    assert thought.proposed_action is not None
    assert label in thought.description
    assert label in thought.proposed_action.title
    assert thought.proposed_action.parameters == {}
    assert label not in str(thought.proposed_action.parameters)

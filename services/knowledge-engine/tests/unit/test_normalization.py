from uuid import uuid4

from nova_knowledge_engine.domain.models import KnowledgeScope
from nova_knowledge_engine.domain.normalization import (
    RawInformation,
    node_id_for,
    normalize,
    slugify,
)


def test_slugify_strips_punctuation_and_lowercases() -> None:
    assert slugify("PostgreSQL") == "postgresql"
    assert slugify("Node.js") == "node-js"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"


def test_slugify_empty_falls_back_to_unnamed() -> None:
    assert slugify("???") == "unnamed"


def test_node_id_for_global_scope_ignores_project_and_user() -> None:
    project_id = uuid4()
    node_id = node_id_for(
        label="Technology",
        name="PostgreSQL",
        scope=KnowledgeScope.GLOBAL,
        project_id=project_id,
        user_id=None,
    )
    assert node_id == "technology:postgresql"


def test_node_id_for_project_scope_folds_in_project_id() -> None:
    project_id = uuid4()
    node_id = node_id_for(
        label="Concept",
        name="API Design",
        scope=KnowledgeScope.PROJECT,
        project_id=project_id,
        user_id=None,
    )
    assert node_id == f"concept:api-design:project:{project_id}"


def test_node_id_for_personal_scope_folds_in_user_id() -> None:
    user_id = uuid4()
    node_id = node_id_for(
        label="Preference",
        name="Dark Mode",
        scope=KnowledgeScope.PERSONAL,
        project_id=None,
        user_id=user_id,
    )
    assert node_id == f"preference:dark-mode:user:{user_id}"


def test_same_name_different_scope_never_collides() -> None:
    a = node_id_for(
        label="Concept", name="X", scope=KnowledgeScope.GLOBAL, project_id=None, user_id=None
    )
    b = node_id_for(
        label="Concept", name="X", scope=KnowledgeScope.PROJECT, project_id=uuid4(), user_id=None
    )
    assert a != b


def test_normalize_trims_whitespace_and_lowercases_domain() -> None:
    raw = RawInformation(
        label="Technology",
        name="  PostgreSQL  ",
        source_type="user",
        domain="  Programming  ",
    )
    candidate = normalize(raw)
    assert candidate.name == "PostgreSQL"
    assert candidate.domain == "programming"
    assert candidate.node_id == "technology:postgresql"

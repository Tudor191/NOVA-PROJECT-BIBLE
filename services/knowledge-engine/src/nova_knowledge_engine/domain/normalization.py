"""Normalization -- formatting/dates/units/names/terminology (docs/design/phase-1/
02-knowledge-engine.md §1-2). Pure, no I/O: never queries `KnowledgeMetadataRepository`
or any store -- that starts at `validation.py`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from nova_knowledge_engine.domain.models import KnowledgeScope, PrivacyLevel

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Deterministic, ASCII-only slug -- e.g. "PostgreSQL" -> "postgresql",
    "Node.js" -> "node-js". Two acquisitions of "the same" name always produce the
    same slug, which is what makes `node_id` derivation an upsert key rather than a
    fresh id every time."""

    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = _SLUG_STRIP_RE.sub("-", normalized.lower()).strip("-")
    return slug or "unnamed"


def node_id_for(
    *,
    label: str,
    name: str,
    scope: KnowledgeScope,
    project_id: UUID | None,
    user_id: UUID | None,
) -> str:
    """Deterministic `node_metadata.node_id` (== the Neo4j node's `id` property).
    Scoped nodes fold `project_id`/`user_id` into the id so the same concept name
    in two different projects (or two different users' personal knowledge) never
    collides -- Part 10's "Personal Knowledge should remain isolated from general
    knowledge" starts at the id, not just at query-time filtering."""

    base = f"{label.lower()}:{slugify(name)}"
    if scope is KnowledgeScope.PROJECT and project_id is not None:
        return f"{base}:project:{project_id}"
    if scope is KnowledgeScope.PERSONAL and user_id is not None:
        return f"{base}:user:{user_id}"
    return base


@dataclass(frozen=True, slots=True)
class RawInformation:
    """Raw input to `domain/acquisition.py`, from any source (Bible Part 10's
    source-agnostic intake, §2's "Knowledge Acquisition" row)."""

    label: str
    name: str
    source_type: str
    domain: str | None = None
    scope: KnowledgeScope = KnowledgeScope.GLOBAL
    project_id: UUID | None = None
    user_id: UUID | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    source_ref: str | None = None
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedCandidate:
    """`RawInformation` after normalization -- name trimmed/title-cased, domain
    lower-cased for consistent grouping, and `node_id` computed."""

    node_id: str
    label: str
    name: str
    source_type: str
    domain: str | None
    scope: KnowledgeScope
    project_id: UUID | None
    user_id: UUID | None
    privacy_level: PrivacyLevel
    source_ref: str | None
    excerpt: str | None


def normalize(raw: RawInformation) -> NormalizedCandidate:
    name = " ".join(raw.name.split())
    domain = raw.domain.strip().lower() if raw.domain else None
    excerpt = raw.excerpt.strip() if raw.excerpt else None
    return NormalizedCandidate(
        node_id=node_id_for(
            label=raw.label,
            name=name,
            scope=raw.scope,
            project_id=raw.project_id,
            user_id=raw.user_id,
        ),
        label=raw.label,
        name=name,
        source_type=raw.source_type,
        domain=domain,
        scope=raw.scope,
        project_id=raw.project_id,
        user_id=raw.user_id,
        privacy_level=raw.privacy_level,
        source_ref=raw.source_ref,
        excerpt=excerpt,
    )

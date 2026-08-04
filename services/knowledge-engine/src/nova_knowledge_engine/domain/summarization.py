"""Knowledge summarization -- condenses a cluster of related nodes into a short
description (docs/design/phase-1/02-knowledge-engine.md §1-2).

Phase 1 implements a structural summary (names, domain, relationship count) rather
than an LLM-generated one -- the AI Model Orchestration Engine that would drive
real natural-language summarization is a Phase 2 deliverable (the same constraint
ADR-009's context section states for embeddings). This keeps the module boundary
and call site correct now, so swapping in an LLM-backed implementation later is a
body-swap, not a redesign.
"""

from __future__ import annotations

from nova_knowledge_engine.domain.models import KnowledgeNode


def summarize_cluster(nodes: list[KnowledgeNode]) -> str:
    if not nodes:
        return ""
    names = ", ".join(sorted({n.name for n in nodes}))
    domains = {n.domain for n in nodes if n.domain}
    domain_note = f" (domain: {', '.join(sorted(domains))})" if domains else ""
    return f"{len(nodes)} related node(s): {names}{domain_note}"

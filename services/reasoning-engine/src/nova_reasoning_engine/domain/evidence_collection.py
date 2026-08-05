"""Hypothesis Verification / Evidence Collection (docs/design/phase-2b/
00-reasoning-engine.md §13) -- Bible Part 8: "Every hypothesis requires
evidence... no important decision should rely on unsupported assumptions."

Checks each `Hypothesis` (§12) against the already-assembled `ContextBundle`
(§7) -- memories, knowledge, and world-model facts -- never issuing a fresh
upstream RPC per hypothesis (that would turn a bounded, parallel
context-assembly fan-out into an unbounded per-hypothesis one, §22).
"""

from __future__ import annotations

from nova_reasoning_engine.domain.models import ContextBundle, Evidence, Hypothesis

__all__ = ["collect_evidence"]

_OVERLAP_THRESHOLD = 0.15
"""Fraction of a hypothesis's words that must appear in a context item's own
text for that item to count as supporting evidence -- a fixed, honestly-
approximate reference point (mirrors the AI Model Orchestration Engine's own
fixed thresholds elsewhere in NOVA), not a learned value."""

_KNOWLEDGE_LAYER_WEIGHT: dict[str, float] = {
    "raw": 0.15,
    "processed": 0.30,
    "verified": 0.55,
    "connected": 0.70,
    "applied": 0.85,
    "expert": 0.95,
    "strategic": 1.0,
}


def _overlap(a: str, b: str) -> float:
    words_a = {w for w in a.lower().split() if w}
    words_b = {w for w in b.lower().split() if w}
    if not words_a:
        return 0.0
    return len(words_a & words_b) / len(words_a)


def collect_evidence(
    hypotheses: list[Hypothesis], context: ContextBundle
) -> tuple[list[Hypothesis], list[Evidence]]:
    """Returns `(hypotheses_with_status, evidence)` -- every hypothesis comes
    back with `status` set to `"supported"` or `"unsupported"` (never left
    `"investigating"`), and every piece of evidence carries a structural
    `weight` derived from its source's own reliability signal, never a
    fabricated weight this engine invents."""
    all_evidence: list[Evidence] = []
    updated_hypotheses: list[Hypothesis] = []

    for hyp in hypotheses:
        supporting: list[Evidence] = []

        for mem in context.memories:
            if _overlap(hyp.description, mem.summary) >= _OVERLAP_THRESHOLD:
                supporting.append(
                    Evidence(
                        hypothesis_id=hyp.id,
                        source="memory",
                        source_ref=str(mem.memory_id),
                        weight=mem.confidence if mem.confidence is not None else 0.5,
                    )
                )

        for kn in context.knowledge:
            if _overlap(hyp.description, kn.name) >= _OVERLAP_THRESHOLD:
                supporting.append(
                    Evidence(
                        hypothesis_id=hyp.id,
                        source="knowledge",
                        source_ref=kn.node_id,
                        weight=round(_KNOWLEDGE_LAYER_WEIGHT.get(kn.layer, 0.3) * kn.confidence, 4),
                    )
                )

        wm = context.world_model
        if wm is not None:
            wm_text = " ".join(filter(None, [wm.objective, wm.task, wm.activity]))
            if wm_text and _overlap(hyp.description, wm_text) >= _OVERLAP_THRESHOLD:
                supporting.append(
                    Evidence(
                        hypothesis_id=hyp.id,
                        source="world_model",
                        source_ref=str(wm.user_id),
                        weight=wm.confidence if wm.confidence is not None else 0.5,
                    )
                )

        all_evidence.extend(supporting)
        status = "supported" if supporting else "unsupported"
        updated_hypotheses.append(hyp.model_copy(update={"status": status}))

    return updated_hypotheses, all_evidence

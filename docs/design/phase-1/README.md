# Phase 1 Technical Design — Memory, Knowledge & World Model Engines

Status: **Draft — pending approval. Implementation does not begin until this design
package is approved**, per explicit instruction.

This is the detailed technical design for Phase 1 of the
[Engineering Roadmap](../../roadmap/ENGINEERING_ROADMAP.md#phase-1--data--memory-substrate),
produced at production-grade depth rather than the lighter "storage and retrieval"
pass the Roadmap originally sketched — see
[00 §Why these three engines get this level of design](00-shared-foundations.md#why-these-three-engines-get-this-level-of-design)
for the reasoning.

## Contents

| Doc | Covers |
|---|---|
| [00 — Shared Foundations](00-shared-foundations.md) | New ADRs (009, 010), new shared packages, conventions common to all three engines |
| [01 — Memory Engine](01-memory-engine.md) | Full design against all 20 requested sections |
| [02 — Knowledge Engine](02-knowledge-engine.md) | Full design against all 20 requested sections |
| [03 — World Model Engine](03-world-model-engine.md) | Full design against all 20 requested sections |
| [04 — Cross-Engine Integration](04-cross-engine-integration.md) | What actually crosses an engine boundary in Phase 1, sequence diagrams, the Phase 2 contract table |

## Review checklist

Before implementation begins, confirm:

- [ ] ADR-009 (`EmbeddingProvider` abstraction) and ADR-010 (standardized embedding
      model: `nomic-embed-text`, 768 dims) are acceptable.
- [ ] The three new shared packages (`nova-vectorstore-sdk`, `nova-graphstore-sdk`,
      `nova-embeddings-sdk`) and their build order are acceptable.
- [ ] The unified `memory_record` schema (discriminated by `memory_type`, extended
      via `type_data` JSONB) vs. one table per memory type — reviewed and accepted.
- [ ] The Postgres-then-graph transactional saga (§17 of docs 02/03) as the answer to
      the cross-datastore consistency problem — reviewed and accepted.
- [ ] Memory Engine owning no graph of its own, delegating all relationships to
      Knowledge Engine ([01 §5](01-memory-engine.md#5-graph-model)) — reviewed and
      accepted as the resolution of Bible Part 3/Part 10's overlapping "relationship"
      language.
- [ ] Performance targets in each engine's §15 are acceptable as Phase 1's
      acceptance bar.
- [ ] The synthetic event harness ([04 §2](04-cross-engine-integration.md#2-synthetic-event-harness-development--testing-until-phase-4))
      as the correct way to test Perception-dependent paths before Phase 4 exists.

Once approved, implementation follows the per-subsystem deliverable checklist in
[SAD 15 §9](../../architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist)
and concludes with an Architecture Review Report per the
[template](../../roadmap/architecture-reviews/TEMPLATE.md), as required for every
phase from Phase 1 onward.

# Phase 2B Technical Design — Reasoning Engine

Implements [Bible Part 8](../../bible/part-08-reasoning-engine.md), cross-referencing
Part 2 ("AI Core & Cognitive Architecture," the narrative introduction ADR-002 already
resolved into four concrete services), Part 9 (Planning Engine, Phase 3, whose boundary
against this engine is one of this document's central concerns), and Part 6 (Cognitive
State Engine / Executive Cognition, Phase 2C/6, whose "continuous background thinking"
loop is explicitly *not* this engine's job).

Status: **Approved. Implemented and Gate-Reviewed (Go), approved by the user.**
This document was approved before any implementation code was written — a
deliberate departure from Phase 2A's precedent (approved to proceed immediately
after its own Gate Review): the user designated the Reasoning Engine one of the
most critical architectural milestones of the entire project and wanted the
architecture validated first, the same validate-before-build discipline Phase 1's
three engines were held to. `reasoning-engine` is now built at production-grade
per this design package, with the
[Architecture Review Report](../../roadmap/architecture-reviews/phase-2b-reasoning-engine.md)
and the formal
[Phase 2B Gate Review](../../roadmap/architecture-reviews/phase-2b-gate-review.md)
filed.

## Contents

| Doc | Covers |
|---|---|
| [00 — Reasoning Engine](00-reasoning-engine.md) | The complete cognitive architecture: pipeline, decision lifecycle, ten reasoning modes, six upstream engine interactions, hypothesis/evidence/alternative/decision mechanics, the structured reasoning trace, data model, ports, events, APIs, and every dimension the user's directive named |

## The one constraint every section of this design defends

Per [ADR-026](../../architecture/adr/ADR-026-reasoning-engine-cognitive-bridge-not-isolated.md),
established at Phase 2A's close specifically ahead of this design work: **the
Reasoning Engine is a cognitive bridge, never an isolated subsystem, and never a
storage layer.** Every significant reasoning process must be able to reference
Long-Term Memory, Knowledge Engine, World Model, Personal Context, Current Goals, and
Available Capabilities. Its responsibility is not storing information — it is
transforming information into decisions. Wherever a design choice in
`00-reasoning-engine.md` looks unusual (why this engine has a Postgres schema despite
"never owns data," why hypothesis generation calls a model but complexity estimation
never does), it is this constraint — and its one narrow, explicitly-reasoned exception
— being defended, and the doc says so explicitly at each such point rather than
leaving the reader to guess.

The second constraint, inherited unchanged from Phase 2A: per
[ADR-020](../../architecture/adr/ADR-020-sole-legal-llm-provider-channel.md), this
engine never imports an LLM/AI provider SDK and never calls one directly. Every model
interaction this engine needs — and it needs many, since generating and evaluating
hypotheses *is* this engine's cognitive work — passes through the AI Model
Orchestration Engine's served Event Bus RPCs, exactly as every other engine's future
model use must.

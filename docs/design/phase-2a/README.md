# Phase 2A Technical Design — AI Model Orchestration Layer

Implements [Bible Part 7](../../bible/part-07-ai-model-orchestration-engine.md).
Builds on [Phase 1's shared foundations](../phase-1/00-shared-foundations.md)
(`nova-contracts`, `nova-observability`, `nova-eventbus-sdk`) and reuses
`nova-embeddings-sdk` (ADR-009) internally as this engine's embedding connector
implementation, rather than duplicating an Ollama embedding client.

Status: **Approved to proceed** — per explicit user directive authorizing Phase 2A
immediately after the Phase 1 Gate Review, this design is produced as part of
implementation (SAD 15 §9 item 1: architecture documentation must exist before
implementation) rather than gated behind a separate pre-implementation approval
round, matching the trust level established over Phase 1.

## Contents

| Doc | Covers |
|---|---|
| [00 — AI Model Orchestration Engine](00-ai-model-orchestration-engine.md) | Full design against the same 20 dimensions used for every Phase 1 engine |

## Why one design doc, not three

Phase 1 had three engines running in parallel with real cross-engine interaction to
design (§4 of that phase's package). Phase 2A is one engine. Phases 2B (Reasoning)
and 2C (Executive Cognition) each get their own design doc when their sub-phase
begins, per the same "documentation is part of the implementation" standing rule —
not bundled into this one, since they are separate sub-phases with separate Gate
Reviews.

## The one constraint every section of the design doc defends

Bible Part 7's own "Architectural Requirements": this engine **must remain
completely independent from Memory, Planning, Knowledge, Personality, World Model,
Executive Cognition, Action, and Capabilities.** It serves only as the intelligence
provider layer. Per [ADR-020](../../architecture/adr/ADR-020-sole-legal-llm-provider-channel.md),
the inverse is also now a permanent rule: no other subsystem may ever depend directly
on an LLM/AI provider — every AI model interaction, present and future, passes
through this engine. Wherever a design choice in `00-ai-model-orchestration-engine.md`
looks unusual (e.g. why "Prompt Pipeline" doesn't fetch memories, why "Function
Registry" doesn't know what tools *do*), it is this constraint being defended, and
the doc says so explicitly at each such point rather than leaving the reader to
guess.

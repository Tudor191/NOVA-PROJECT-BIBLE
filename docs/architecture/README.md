# NOVA Software Architecture Document (SAD)

This is the official engineering blueprint for implementing NOVA, derived from the
[NOVA Project Bible](../bible/README.md). Start with
[00 — Overview & Architecture Decision Records](00-overview-and-decisions.md), which
explains how this document set was produced and records the key architectural
decisions (and the reasoning behind them) that every other document builds on.

## Contents

| # | Document |
|---|----------|
| 00 | [Overview & Architecture Decision Records](00-overview-and-decisions.md) |
| 01 | [Technology Stack](01-technology-stack.md) |
| 02 | [Repository & Folder Structure](02-repository-and-folder-structure.md) |
| 03 | [Backend Architecture](03-backend-architecture.md) |
| 04 | [Frontend Architecture](04-frontend-architecture.md) |
| 05 | [Desktop Application Architecture](05-desktop-architecture.md) |
| 06 | [AI Layer Architecture](06-ai-layer-architecture.md) |
| 07 | [Database Architecture](07-database-architecture.md) |
| 08 | [Memory Architecture](08-memory-architecture.md) |
| 09 | [Event Bus Architecture](09-event-bus-architecture.md) |
| 10 | [Inter-Engine Communication Flows](10-inter-engine-communication.md) |
| 11 | [API Architecture](11-api-architecture.md) |
| 12 | [Agent Architecture — NOVA Agent Operating System](12-agent-architecture.md) |
| 13 | [Authentication & Security Architecture](13-auth-and-security.md) |
| 14 | [Deployment Architecture](14-deployment-architecture.md) |
| 15 | [Development Workflow](15-development-workflow.md) |
| 16 | [Testing Strategy](16-testing-strategy.md) |
| 17 | [CI/CD Pipeline](17-cicd-pipeline.md) |
| 18 | [Local-First & Cloud Sync](18-local-first-and-cloud-sync.md) |
| 19 | [Scalability Strategy](19-scalability-strategy.md) |
| 20 | [Engine Responsibility Boundaries — Memory, Knowledge, World Model](20-engine-responsibility-boundaries.md) |
| 21 | [AI Model Orchestration Philosophy](21-ai-model-orchestration-philosophy.md) |
| 22 | [NOVA Human Interaction Principles](22-nova-human-interaction-principles.md) |

See also: [Engineering Roadmap](../roadmap/ENGINEERING_ROADMAP.md) — the phased
implementation plan built on top of this SAD, and
[Architecture Decision Records](adr/README.md) — the structured, per-subsystem ADR
log (Context/Problem/Alternatives/Decision/Consequences/Tradeoffs/Future
implications) filed for every significant decision made *during* implementation,
complementing ADR-001 through ADR-010 below.

## Revision history

- **v1.3** — Doc 21 (AI Model Orchestration Philosophy, filed at Phase 2A's
  completion) and Doc 22 (NOVA Human Interaction Principles, filed alongside the
  [Phase 2D Master Architectural Blueprint](../design/phase-2d/00-master-blueprint.md)
  as its permanent philosophical companion) added to this index — both existed
  before this entry but were missing from the Contents table.
- **v1.2** — Doc 20 added: the canonical Memory/Knowledge/World Model responsibility
  boundary reference, written on Phase 1 completion per explicit user directive, and
  declared the reference every future engine's design must be checked against. The
  structured `adr/` directory established as the permanent home for per-decision ADRs
  going forward (ADR-011 onward), a new standing requirement for every completed
  subsystem.
- **v1.1** — Event Bus (ADR-006) and Graph Store (ADR-007) promoted to explicit,
  swappable interfaces per approval conditions on NATS and Neo4j; Agent Orchestrator
  redesigned as the standalone NOVA Agent Operating System (ADR-008); the **10x Test**
  added as a mandatory design rule applied to every decision in this document set
  going forward (see [00](00-overview-and-decisions.md#the-10x-test)).
- **v1.0** — Initial SAD: technology stack, repository structure, and all 19
  architecture domains requested by the user, plus the companion Engineering Roadmap.

## Status

**Draft v1.1 — Technology stack, Event Bus, Graph Store, and Agent Architecture
approved with conditions (all incorporated above); remaining sections pending final
review.** No implementation code exists yet. Per the project's governing instruction
(the Bible's System Instruction section), this architecture is proposed for review and
confirmation before Phase 0 implementation begins.

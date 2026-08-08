# Architecture Decision Records

This directory is the official, permanent log of significant architectural
decisions made *during implementation* — as distinct from ADR-001 through ADR-010,
which are recorded inline in
[`00-overview-and-decisions.md`](../00-overview-and-decisions.md) as the
foundational decisions made *during design*, before any code existed.

**Standing requirement (established during Phase 1, permanent going forward):**
whenever a subsystem is completed, every significant architectural decision made
while building it gets filed here as its own ADR, using the structure below. The
goal is that any major architectural decision in NOVA remains traceable years from
now, independent of whoever's memory of "why did we do it this way" would otherwise
be the only record.

## Format

Every ADR in this directory follows the same seven-section structure:

1. **Context** — the situation that made a decision necessary.
2. **Problem** — the specific question being answered, stated precisely enough that
   a reader unfamiliar with the surrounding work could evaluate the alternatives.
3. **Alternatives considered** — what else was on the table, and why each one lost.
4. **Decision** — what was actually chosen, concretely.
5. **Consequences** — what follows mechanically from the decision (new invariants,
   new coupling, new capabilities).
6. **Tradeoffs** — what was explicitly given up, phrased so a future reader can tell
   whether the conditions that made the trade acceptable still hold.
7. **Future implications** — what changes (or must be revisited) if circumstances
   change; what a future engine building on top of this should know.

## Numbering

Numbering continues the existing ADR-001 through ADR-010 sequence rather than
restarting — this is one log, split across two locations for historical reasons
(design-time decisions predate this directory's existence). New ADRs are always the
next unused number, regardless of which subsystem they originate from.

## Index

| ADR | Title | Subsystem(s) |
|---|---|---|
| [011](ADR-011-unified-memory-record-schema.md) | Unified `memory_record` schema over one table per memory type | Memory Engine |
| [012](ADR-012-redis-as-primary-store-not-cache.md) | Redis as the primary store for Working Memory and Active Context, not a cache | Memory Engine, World Model Engine |
| [013](ADR-013-async-off-path-embedding-generation.md) | Asynchronous, off-write-path embedding generation | Memory Engine, Knowledge Engine |
| [014](ADR-014-postgres-then-graph-two-phase-saga.md) | Postgres-then-graph two-phase saga via transactional outbox | Knowledge Engine, World Model Engine |
| [015](ADR-015-knowledge-maturity-lifecycle.md) | Seven-stage knowledge-maturity lifecycle over a single confidence score | Knowledge Engine |
| [016](ADR-016-contradiction-recording-not-overwriting.md) | Contradictions are recorded, never silently resolved by overwrite | Knowledge Engine |
| [017](ADR-017-world-model-boundary-separation.md) | World Model boundary: no embeddings, no forgetting lifecycle, no validated-fact graph | World Model Engine |
| [018](ADR-018-world-object-state-reads-from-postgres.md) | World Object "current state" reads come from Postgres, never Neo4j | World Model Engine |
| [019](ADR-019-deferred-idle-sweep-worker.md) | The idle-sweep worker is deliberately deferred, not shipped half-correct | World Model Engine |
| [020](ADR-020-sole-legal-llm-provider-channel.md) | AI Model Orchestration Engine is the only legal channel to any LLM/AI provider — no exceptions | AI Model Orchestration Engine; binding on every subsystem from Phase 2A onward |
| [021](ADR-021-deterministic-explainable-routing.md) | Deterministic, explainable model routing with mandatory structured telemetry | AI Model Orchestration Engine |
| [022](ADR-022-stateless-cognitive-gateway.md) | The AI Model Orchestration Engine is a stateless cognitive gateway | AI Model Orchestration Engine |
| [023](ADR-023-uniform-connector-compliance-suite.md) | Every provider connector passes one identical compliance test suite | AI Model Orchestration Engine |
| [024](ADR-024-interface-versioning-from-day-one.md) | Every public interface is versioned from the beginning | AI Model Orchestration Engine; binding on every subsystem's public interfaces from Phase 2A onward |
| [025](ADR-025-personal-edition-is-the-flagship.md) | The Personal Edition is NOVA's flagship; every commercial/enterprise edition is strictly derived from it | NOVA-wide; binding on every engine, every phase, from this point forward |
| [026](ADR-026-reasoning-engine-cognitive-bridge-not-isolated.md) | The Reasoning Engine is a cognitive bridge, never an isolated subsystem | Reasoning Engine (Phase 2B); binding on its design doc and every subsequent implementation decision |
| [027](ADR-027-executive-cognition-coordinates-never-owns-intelligence.md) | Executive Cognition coordinates cognitive subsystems, never owns intelligence | Executive Cognition Engine (Phase 2C); binding on its design doc and every subsequent implementation decision |
| [028](ADR-028-executive-cognition-defers-to-specialized-engine-authority.md) | Executive Cognition is policy-driven, not intelligence-driven: specialized engines are epistemically authoritative in their own domain | Executive Cognition Engine (Phase 2C); binding on its design doc and every subsequent implementation decision |
| [029](ADR-029-executive-cognition-optimizes-long-term-user-objectives.md) | Executive Cognition arbitration optimizes for the user's long-term objectives, not only the current request | Executive Cognition Engine (Phase 2C); operationalizes ADR-025's Priority 1 (Personal Intelligence) |
| [030](ADR-030-personality-stores-digital-twin-learns.md) | Personality Engine stores and applies resolved preferences; Digital Twin Engine is the sole epistemic learner | `personality-engine` (Phase 2D-A), `digital-twin-engine` (Phase 2D-D); binding on both engines' TDDs and every subsequent implementation decision |
| [031](ADR-031-subjective-experience-quality-is-a-first-class-requirement.md) | Subjective experience quality (natural, responsive, consistent) is a first-class requirement and standing tiebreaker among architecture-compliant implementation options | NOVA-wide; binding on every engine, every phase, from this point forward — generalizes Master Blueprint §13.2's latency-specific instance |
| [032](ADR-032-identity-confidence-is-also-an-authorization-signal.md) | Identity confidence is also an authorization signal: future privileged capabilities (automation, smart-home, financial, security-sensitive) must gate on configurable identity-confidence thresholds, never on a binary identity check | `perception-engine` (Phase 2D-B); binding on every future engine that gates a privileged capability — Action Engine (Phase 3/NAOS), Autonomy Engine (Phase 4), and beyond |
| [033](ADR-033-test-infrastructure-boundary-and-two-tier-testing.md) | Test infrastructure dependencies are development/test-only, never production; integration testing is a permanent two-tier model (fake-backed + real-infrastructure), neither tier retiring the other | `nova-testkit`; binding on every engine's `tests/` directory and every future shared test-infrastructure package, from this point forward |

See also: [Phase 1 Architecture Review Report](../../roadmap/architecture-reviews/phase-1-data-memory-substrate.md)
and [Doc 20 — Engine Responsibility Boundaries](../20-engine-responsibility-boundaries.md),
both produced alongside this ADR set on Phase 1's completion. ADR-020 through
ADR-024 were added during Phase 2A, before its first production connector was
considered complete. ADR-025 was added mid-Phase-2A, per explicit user directive
establishing NOVA's Personal Edition as its permanent flagship and reference
implementation. ADR-026 was added at Phase 2A's close, ahead of Phase 2B design
work, establishing the Reasoning Engine's boundary before its design doc is
written — the same sequencing ADR-017 followed for World Model Engine in Phase 1.
ADR-027 was added at Phase 2B's close, ahead of Phase 2C design work, establishing
the Executive Cognition Engine's boundary before its design doc is written — the
same sequencing again, one layer higher in the cognitive stack. ADR-028 and ADR-029
were added after the Phase 2C design doc's own approval but before implementation
began, per explicit user directive establishing two further permanent principles —
epistemic deference to specialized engines, and long-term-objective optimization as
a Personal Edition default — ahead of any Executive Cognition Engine code being
written. ADR-030 was filed after both Phase 2D-A TDDs (`communication-engine`,
`personality-engine`) were drafted and approved, rather than before as the Master
Blueprint originally committed to — a sequencing deviation the ADR itself records
honestly (its own "Process note") rather than silently correcting; the boundary it
formalizes was never actually violated in either TDD, only the filing order.
ADR-031 was added after approving the AI Model Orchestration speech extension and
authorizing continued Phase 2D-A implementation, per explicit user directive
generalizing Master Blueprint §13.2's latency-specific principle into a permanent,
NOVA-wide standing rule. ADR-032 was added after approving the Phase 2D-B
Technical Design Document (`perception-engine`) and authorizing its
implementation to begin, per explicit user directive extending that document's
evidence-fusion identity-confidence model into a permanent, NOVA-wide principle
governing every future privileged-capability engine's authorization logic.
ADR-033 was added after approving the `nova-testkit` Technical Implementation
Plan (STEP 2 of the Project Health Review's approved 5-step plan) and
authorizing its implementation to begin, per explicit user directive to file
one ADR covering the two permanent rules that plan's design depends on: the
test-infrastructure dev-only dependency boundary, and the fake-backed/
real-infrastructure two-tier testing model.

# Phase 2D Design — Voice, Identity, Conversation & Companion

Implements [Bible Part 13](../../bible/part-13-communication-engine.md)
(Communication Engine) in full, [Part 17](../../bible/part-17-personality-engine.md)
(Personality Engine) in full, and the first, deliberately minimal slices of
[Part 11](../../bible/part-11-perception-engine.md) (Perception Engine — voice and
face/presence modalities only) and
[Part 16](../../bible/part-16-digital-twin-engine.md) (Digital Twin Engine —
Communication Profile and conversation-scoped Preferences only), cross-referencing
Part 6 ("NOVA Cognitive State Engine," a *separate* future service this design
draws an explicit boundary against — see the blueprint's §9.4) and
[ADR-025](../../architecture/adr/ADR-025-personal-edition-is-the-flagship.md)
(Personal Edition priority order, directly governing this phase's scope choices).

Status: **Blueprint approved. Doc 22 and Doc 23 approved. Both Phase 2D-A
Technical Design Documents (01 — Communication Engine, 02 — Personality Engine)
approved. Phase 2D-A is implemented and Gate-Reviewed (Go — the real-Postgres-
verification recommendation remains an explicitly open, tracked item, to be
closed as soon as a Docker-capable environment is available) — see the
[Architecture Review Report](../../roadmap/architecture-reviews/phase-2d-a-voice-communication-foundation.md)
and the
[Gate Review](../../roadmap/architecture-reviews/phase-2d-a-gate-review.md).**
Phase 2D-B (03 — Perception Engine) is implemented and Gate-Reviewed (Go —
the real-Postgres-verification recommendation now covers three engines,
personality-engine/communication-engine/perception-engine, remaining an
explicitly open, tracked item) — see the
[Architecture Review Report](../../roadmap/architecture-reviews/phase-2d-b-identity-presence.md)
and the
[Gate Review](../../roadmap/architecture-reviews/phase-2d-b-gate-review.md).**
Cumulative Production SLOC crossed the 30,000 Project Health Review reminder
threshold this phase (31,610 SLOC) — flagged explicitly, pending the user's
decision on whether to act on it before Phase 2D-C.
Phase 2D-C (04 — Conversation Intelligence) is implemented (Option B, per
direct user approval of the TDD's §0.4 fork) and Gate-Reviewed — see the
[Gate Review](../../roadmap/architecture-reviews/phase-2d-c-gate-review.md)
for the explicit four-part breakdown of what is fully verified, what is
verified only through contract-level fakes, and what remains genuinely
unverified end-to-end pending `perception-engine`'s still-unwired
production signal chain and the newly-discovered, unbuilt
`communication-engine`↔`reasoning-engine` integration loop.
**Phase 2D-C Closure (05 — Conversation Intelligence Closure)** closes the
Gate Review's six disclosed gaps in dependency order — see the
[closure design document](05-conversation-intelligence-closure.md) for the
full dependency analysis, per-priority technical designs, and remaining
open architectural forks. **Priority 3 (the communication-engine ↔
reasoning-engine conversation loop) is approved and implemented** — see the
[Priority 3 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-3-gate-review.md).
**Priority 1 (perception-engine's production signal chain, including a new
`POST /v1/perception/observations` ingestion endpoint) is approved and
implemented** — see the
[Priority 1 Gate Review](../../roadmap/architecture-reviews/phase-2d-c-closure-priority-1-gate-review.md)
for the disclosed capability limit (no identity matching or session-active
signal yet, pending Priority 2).
**Priorities 2, 4, 5, and 6 remain design-only, not yet implemented and
not yet user-approved**, each awaiting its own explicit go-ahead before any
further code changes. Phase 2D-D does not start until the full closure is
explicitly approved.
Per direct user instruction, this phase was preceded by a full architectural
blueprint and two permanent governing documents *before* any individual engine's
TDD, the same "validate the architecture before designing a single engine"
discipline applied one level higher: here, to an entire phase's worth of engines
at once, not just one.

**A note on naming:** this work was originally requested under the working name
"Phase 3" (sub-phases 3A–3D). It has been reconciled against the existing roadmap
as **Phase 2D**, split into sub-phases 2D-A through 2D-D — the roadmap's existing
Phase 3 (Planning & the NOVA Agent Operating System) is unrelated and unchanged.
See the blueprint's §0 for the full reconciliation and the exact 3A→2D-A / 3B→2D-B
/ 3C→2D-C / 3D→2D-D mapping.

## Contents

| Doc | Covers |
|---|---|
| [00 — Master Architectural Blueprint](00-master-blueprint.md) | Why Phase 2D exists, what separates it from Phases 2A–2C, explicit in/out-of-scope boundaries, the four sub-phases (2D-A Voice & Communication Foundation, 2D-B Identity & Presence, 2D-C Conversation Intelligence, 2D-D Personal Companion) and their responsibilities, the talking-TO-vs-ABOUT-NOVA addressee-detection boundary, cross-engine communication model, data ownership matrix, API/RPC/statelessness matrix, reconciliation with already-canonical Bible engines (Perception, Digital Twin, Cognitive State), dependency graph, architectural risks, and alignment with NOVA's long-term-companion vision |
| [01 — Communication Engine](01-communication-engine.md) | Phase 2D-A's transport/lifecycle layer: the required speech-modality extension to `ai-model-orchestration-engine` (ADR-020 compliance), the `ConversationSession` state machine, the audio pipeline and barge-in, the `communication.intent` gate (ADR-005 enforcement), the honest interim for addressee detection ahead of Phase 2D-B/C, data model, event contracts, APIs, and Doc 22/23 compliance mapping |
| [02 — Personality Engine](02-personality-engine.md) | The rule-based, model-free (ADR-020-compliant-by-construction) implementation of Doc 23: the Consistency Validator, Style Selector, Personality Memory (a static default until Phase 2D-D's `digital-twin-engine` exists to populate it for real), the Personality/Digital-Twin boundary enforced structurally, data model, event/API contracts, and Doc 22/23 compliance mapping |
| [03 — Perception Engine](03-perception-engine.md) | Phase 2D-B's minimal (voice + camera) slice of Bible Part 11: the required biometric/wake-signal extension to `ai-model-orchestration-engine` (ADR-020 compliance) and the required `ActiveContext` extension to World Model Engine (ADR-017 compliance), the Sensor Abstraction Layer's full lifecycle contract, the Identity Registry, the evidence-fusion identity-confidence algorithm (no single signal is ever sufficient), the talking-TO-vs-ABOUT-NOVA boundary (2D-B observes and publishes, 2D-C decides), privacy/consent architecture, data model, event/API contracts, and Doc 22/23 compliance mapping. **Approved and implemented.** |
| [04 — Conversation Intelligence](04-conversation-intelligence.md) | Phase 2D-C's behavioral/policy extension to `communication-engine`: addressee-detection fusion (2D-B signals + conversational context), the silence/interruption policy layer, the Clarification Engine, response-length/tone/multilingual-response shaping, session-scoped Conversation Memory, one disclosed open architectural fork requiring the user's decision (perception-engine's unwired production signal path), three disclosed small required cross-engine extensions, and Doc 22/23/ADR compliance mapping. **Approved and implemented, Option B — see the [Gate Review](../../roadmap/architecture-reviews/phase-2d-c-gate-review.md) for exactly what is and isn't verified end-to-end.** |
| [05 — Conversation Intelligence Closure](05-conversation-intelligence-closure.md) | Closes the Gate Review's six disclosed production-readiness gaps in dependency order: perception-engine's real production signal chain, the `user_id`/session-correlation problem, the missing communication-engine↔reasoning-engine conversation loop, the cross-context "start listening" mechanism, personality-engine's inert `channel` parameter, and real-infrastructure verification status — with a full dependency graph, per-priority technical designs backed by direct code investigation, and three open architectural forks. **Design only, not yet implemented, not yet user-approved.** |

**Companion documents (not phase-scoped — permanent):**
[Doc 22 — NOVA Human Interaction Principles](../../architecture/22-nova-human-interaction-principles.md)
and [Doc 23 — NOVA Personality Specification](../../architecture/23-nova-personality-specification.md)
are the philosophical and character constitutions this blueprint, and every future
communication-related engine after it, are checked against. Doc 22 governs *when
and how NOVA interacts* (silence, interruption cost, addressee detection, privacy
architecture); Doc 23 governs *who NOVA is while interacting* (identity, traits,
values, ethics, voice — directly binding on `personality-engine`'s eventual TDD).
Both live in `docs/architecture/` rather than here because neither is specific to
Phase 2D — they govern Perception's later Phase 4 extension, Digital Twin's later
Phase 4 extension, and Executive Cognition's Phase 6 coordination of Communication
exactly as much as they govern this phase.

## The one constraint every section of this blueprint defends

**Phase 2D is where a human first becomes a first-class architectural concern, not
just an API caller** — every design choice in `00-master-blueprint.md` that looks
unusual (why `perception-engine` and `digital-twin-engine` are stood up now, in
deliberately narrow form, instead of waiting for their "official" Phase 4 slot; why
Perception is forbidden from containing any "should I respond" logic even though it
sits right next to the decision that needs its signals; why Personality and Digital
Twin split what the Bible describes as almost the same fact) is this constraint, and
the discipline established across Phases 2A–2C (minimal-now/full-later, explicit
boundary ADRs at phase transitions, honest scope with no fabricated capability)
being applied to an entire phase's worth of engines at once — and the document says
so explicitly at each such point rather than leaving the reader to guess.

The two constraints inherited unchanged from every prior phase:
[ADR-004](../../architecture/00-overview-and-decisions.md#adr-004--event-bus-is-the-only-legal-cross-engine-channel)
(Event Bus is the only legal cross-engine channel — no exceptions for the new
Perception/Digital-Twin RPCs) and
[ADR-005](../../architecture/00-overview-and-decisions.md#adr-005--nova-never-speaks-except-through-the-communication-engine)
(no engine, including the three new ones this phase introduces, ever renders
user-facing output except through `communication-engine`).

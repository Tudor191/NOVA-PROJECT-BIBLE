# ADR-025 — The Personal Edition is NOVA's flagship; every commercial/enterprise edition is strictly derived from it

**Subsystem(s):** NOVA-wide — binding on every engine, every phase, from this point forward
**Status:** Accepted — permanent architectural principle

## Context

Bible Part 1's own subtitle reads "Enterprise Artificial Intelligence Operating
System," and the roadmap already carries two later phases framed around
multi-user/organizational deployment — Phase 7 ("Security, Governance & Enterprise
Readiness") and Phase 8 ("Scale-Out & Cloud/Enterprise Deployment"), with SAD 19 §3
describing a multi-tenant model (schema-per-tenant Postgres, tenant-scoped Neo4j,
`user_id`/`tenant_id` sharding keys). SAD 00's guiding constraint #3 already leans
personal-first ("NOVA must run at zero cost, fully offline, on a single user's
machine... Cloud and enterprise capability is an additive deployment mode, not a
prerequisite"), but nothing in the architecture record made that ranking explicit,
permanent, or binding on future tradeoffs.

The user has now stated this directly and unambiguously: NOVA is first and foremost
their personal AI Operating System. The primary objective is not to build a
commercial product; it is to build the most capable, intelligent, and deeply
personalized AI companion possible for a single trusted user. Whenever a tradeoff
exists between enterprise features and personal capabilities, personal capabilities
win. The architecture must stay modular and scalable enough that a commercial
edition can be built later without a redesign, but enterprise requirements must
never reduce or compromise the Personal Edition's capabilities. The Personal Edition
is always the reference implementation; any future public/commercial edition is
derived from it, never the reverse, and may omit or simplify capabilities that are
only useful for a deeply personalized system — but the Personal Edition itself must
never lose capability to make that future edition easier to build.

The user also established a permanent priority order for future development,
independent of the roadmap's phase sequence:

1. **Personal Intelligence** — NOVA continuously learns how the user thinks, works,
   and makes decisions: their long-term projects, coding style, workflows, goals,
   interests, and routines. Its purpose is not to answer questions; its purpose is
   to become increasingly effective at helping the user accomplish real work.
2. **Long-Term Memory** — one of NOVA's strongest capabilities, not merely a storage
   system: remembering important information for years, retrieving it intelligently,
   connecting related experiences, and continuously improving its understanding of
   the user. A competitive advantage, not a database.
3. **Personal Automation** — automating repetitive work wherever possible: project
   management, development workflows, file organization, research, documentation,
   code generation, environment setup, reminders, daily planning, and information
   summarization.
4. **Natural Interaction** — voice interaction, contextual conversation, continuous
   awareness, and proactive assistance becoming first-class capabilities, so every
   subsystem contributes to NOVA feeling like a cognitive partner rather than
   software.

## Problem

Without an explicit, binding rule, two failure modes become likely as the roadmap
reaches Phases 3 through 8:

1. **Quiet genericity creep.** Building toward an eventual multi-user/enterprise
   audience naturally pulls design decisions toward the lowest common denominator —
   configurable-for-anyone instead of deeply tuned for one person — the same failure
   mode that makes most "AI assistant" products shallow. A future engine could end up
   architected for a hypothetical tenant that doesn't exist yet, at the expense of
   the actual user who does.
2. **No resolution order for real tradeoffs.** Later phases (Reasoning Engine's
   personalized decision-making, Long-Term Memory's retrieval depth, Perception's
   habit modeling, Personality's identity consistency) will repeatedly face a choice
   between a capability that only makes sense for a single, deeply known user and a
   capability that generalizes across unknown users or organizations. Without a
   standing answer, each engine's implementer (including a future instance of this
   same coding agent) would have to re-derive the right answer from scratch, and
   could get it wrong in either direction — over-investing in genericity too early,
   or accidentally coupling personal-only assumptions into a path enterprise mode
   also has to execute.

## Alternatives considered

- **Build one general-purpose, configurable platform from the start, with personal
  and enterprise as symmetric configurations of the same generic system.** Rejected:
  this is the exact failure mode being guarded against — a system designed to be
  equally suited to any user ends up deeply suited to none. Depth of personalization
  and breadth of generic configurability are in real tension, and this project has
  been told explicitly which one wins.
- **Design and build a Commercial/Enterprise Edition first (or in parallel), with
  Personal Edition as a restricted subset of it.** Rejected: the direct reverse of
  the user's instruction, and also the pattern behind why most enterprise SaaS AI
  products feel impersonal — the product is built for an abstract organization first,
  a specific person never.
- **Fork the codebase into two products once commercial need actually arises.**
  Rejected: violates ADR-001's modular-monolith-first design (every module
  independently deployable, no redesign required to change deployment topology) and
  the Bible's explicit "must support evolution without fundamental redesign." A fork
  guarantees permanent drift — every future Personal Edition improvement would need
  manual backporting to stay available commercially, exactly the outcome this ADR
  exists to prevent.

## Decision

1. **The Personal Edition is the only edition actively built through the current
   roadmap (Phases 1 through 6), and remains the reference implementation
   permanently.** Every engine, by default, is designed and configured for a single
   trusted user — "who is calling" never requires an organization/tenant model to
   answer unless enterprise mode is explicitly enabled.
2. **A future Commercial/Enterprise Edition is a strictly derived, additive
   deployment mode of the same codebase — never a parallel product, never a
   redesign.** Multi-tenancy (SAD 19 §3), admin/governance controls (SAD 13), and any
   enterprise-only surface must be built as optional layers switched on by
   configuration or deployment topology (mirroring ADR-001's local-first-vs-cloud
   pattern: same modules, same business logic, different composition), never as
   changes to a shared code path that Personal Edition mode also executes.
3. **Personal capability wins ties.** Whenever a design decision trades off depth of
   personalization (memory depth, learned-preference modeling, workflow automation
   tuned to one person's actual habits) against breadth of genericity (configurable
   for arbitrary users, tenant-isolation overhead paid on every request, generic
   admin surfaces), the personal-depth option is chosen by default. A future
   Commercial Edition may then explicitly restrict, simplify, or disable that
   capability for its own deployment constraints — but the Personal Edition's own
   implementation must never be held back, slowed down, or left unbuilt in order to
   make that future restriction easier to build.
4. **The priority order in the Context section governs in-phase scope decisions, not
   the phase sequence.** The roadmap's Phase 2A → 6 structural sequence
   (Orchestration → Reasoning → Executive Cognition → Voice → Planning/NAOS →
   Perception/Autonomy → Desktop → full orchestration) is unchanged by this ADR.
   What changes is: whenever a phase has latitude in *what* to build first or how
   deep to build it, Personal Intelligence > Long-Term Memory > Personal Automation
   > Natural Interaction is the resolution order.

## Consequences

- Every future engine's `Settings`/config defaults to single-user, single-tenant
  operation; enterprise mode is something a deployment turns on, never something
  Personal Edition code has to route around.
- Phase 7 and Phase 8 remain exactly where they are in the roadmap (after the
  cognitive/interaction phases, not before) — nothing about their position or
  content changes here, only the standard they're held to. Their Objectives and
  Acceptance Criteria must be worded so "adds enterprise capability" never implies
  "modifies or gates Personal Edition capability," and each of their Gate Reviews
  must explicitly verify Personal Edition behavior is unaffected by enterprise mode
  being present in the codebase.
- Bible Part 1's subtitle ("Enterprise Artificial Intelligence Operating System") is
  superseded by this ADR for all engineering purposes going forward. Part 1 itself
  is amended with a short, dated note pointing here rather than silently rewritten —
  the Bible's history stays traceable, the same discipline this ADR log itself
  follows.
- Any future ADR or design doc that reaches a personal-vs-commercial tradeoff must
  cite this ADR and default to the personal-capability answer unless the user
  explicitly overrides it for that specific case.

## Tradeoffs

- A future Commercial/Enterprise Edition may take longer to reach feature parity
  with generic SaaS competitors on breadth (self-serve onboarding, admin dashboards,
  configurable-for-anyone flexibility), because those are explicitly lower priority
  than personal depth. Accepted — the user has stated directly that NOVA is not
  being built to maximize the number of users; it is being built to maximize the
  value it provides to its primary user.
- Engineering effort that would normally go into speculative genericity from day one
  (pluggable per-tenant policy engines, generic admin surfaces, configuration
  matrices for hypothetical deployments) is deferred until Phase 7/8 actually need
  it. Accepted — this reinforces, rather than conflicts with, the project's standing
  "evidence-driven optimization, no speculative generality" instruction already in
  force since Phase 1.

## Future implications

- When Phase 7/8 design work actually begins, its first deliverable should be a
  compatibility review confirming no Personal Edition code path was implicitly
  weakened by any decision made in Phases 2–6 under this ADR's assumption that
  enterprise concerns are additive.
- If a genuine conflict is ever found where a Personal Edition capability cannot be
  built without first building enterprise-shaped infrastructure, that conflict must
  be escalated to the user rather than silently resolved in the enterprise
  direction.
- Every completed phase's Architecture Review Report should include a short note
  confirming the phase's deliverables were evaluated against this ADR's priority
  order (Personal Intelligence > Long-Term Memory > Personal Automation > Natural
  Interaction) where the phase had scope latitude.

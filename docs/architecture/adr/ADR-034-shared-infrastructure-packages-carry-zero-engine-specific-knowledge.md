# ADR-034 — Shared infrastructure packages carry zero engine-specific knowledge

**Subsystem(s):** `nova-service-kit`; binding on every future shared
infrastructure package, from this point forward
**Status:** Accepted — permanent architectural principle

## Context

The Project Health Review (August 2026) quantified ~700 lines of pure
structural boilerplate duplicated across `api/health.py`, `repository/db.py`,
`repository/outbox_dispatcher.py`, and `workers/__init__.py` (§18, §27.2). The
user approved a proposal
(`docs/design/nova-service-kit/boilerplate-extraction-proposal.md`) to extract
the first three into a new shared package, `nova-service-kit`, then approved
implementation of that proposal's first wave (Extractions A, B, C, D).

The proposal itself (§5) specified an import-linter contract for
`nova-service-kit` modeled directly on ADR-033's existing `nova-testkit`
contract, and recommended (§13) that this be generalized into its own ADR
rather than special-cased to one package — this is that ADR.

## Problem

`nova-service-kit` is the second shared package in this codebase whose entire
purpose is being imported by every engine (the first being `nova-testkit`,
governed by ADR-033, which is dev/test-only). Without a binding rule, nothing
prevents `nova-service-kit` from accumulating engine-specific special cases
over time — an `if engine_name == "knowledge-engine"` branch here, an optional
parameter that only one engine ever passes there — each individually
reasonable, collectively turning a boilerplate remover into a hidden
coupling point no single engine team owns or can safely change alone. This is
exactly the "generic shared package that grows without a stable reason to
exist" failure mode the proposal was explicitly asked to avoid (boilerplate
extraction proposal, task item 8).

## Alternatives considered

- **No formal rule — trust the proposal's own scope statement
  (`docs/design/nova-service-kit/boilerplate-extraction-proposal.md` §5) to
  hold by convention.** Rejected for the same reason ADR-033 rejected this for
  `nova-testkit`'s dependency boundary: a convention with nothing to catch a
  future violation is not a guarantee, and this project has already found one
  canonical document (`16-testing-strategy.md`) that described a boundary as
  real when nothing enforced it.
- **One import-linter contract per shared package, worded independently each
  time.** Rejected as unnecessary duplication of the *rule itself* (as
  opposed to the boilerplate this ADR's own subject package removes) — the
  rule is identical in shape to ADR-033's, and deserves one standing
  statement future shared packages inherit, not a re-derived one each time.
- **Fold this into ADR-033 directly**, extending its scope from
  "test infrastructure" to "all shared infrastructure." Rejected: ADR-033 is
  specifically about the dev/test-only dependency boundary and the two-tier
  testing model — two concerns unrelated to `nova-service-kit`, which is a
  *production* dependency for the engines it serves (the opposite of
  `nova-testkit`'s dev-only status). Conflating them would blur two boundary
  rules that need to stay independently legible.

## Decision

1. **Any shared package whose purpose is infrastructure plumbing consumed
   identically by multiple engines must carry zero engine-specific
   knowledge** — no import of any engine's own top-level package, no
   conditional behavior keyed on a specific engine's name or identity, no
   parameter whose only ever-passed value is specific to one engine's
   internal concept (an *engine-supplied* value used generically, like
   `nova-service-kit`'s `make_health_router(health_status=...)` callback, is
   fine; a hardcoded branch inside the shared package for one engine's
   special case is not).
2. **This is enforced structurally, not just by convention**: a
   forbidden-import contract naming the shared package as the source and
   every engine's top-level package as forbidden targets, mirroring
   ADR-033's existing `nova-testkit` contract exactly in mechanism:
   ```toml
   [[tool.importlinter.contracts]]
   name = "nova-service-kit has no engine-specific knowledge (ADR-034): it may not import any engine's own top-level package"
   type = "forbidden"
   source_modules = ["nova_service_kit"]
   forbidden_modules = [ /* every engine's top-level package */ ]
   ```
3. **This rule generalizes to every future shared infrastructure package**,
   not `nova-service-kit` alone — the same way ADR-033's rule already applies
   to any future shared *test*-infrastructure package. A future shared
   package (for example, the middleware layer discussed in the Project
   Health Review §27.3) inherits this rule automatically; it does not need
   its own ADR to restate it, only its own import-linter contract entry
   applying the same shape.
4. **Unlike `nova-testkit` (ADR-033), `nova-service-kit` is a production
   dependency.** Every consuming engine declares it under `[project]
   dependencies`, not `[dependency-groups] dev` — this is the intended,
   correct difference between the two packages, not an inconsistency. ADR-033's
   dev-only rule is specific to test infrastructure and does not apply here;
   this ADR's zero-engine-specific-knowledge rule is the analogous but
   distinct guarantee for production infrastructure.

## Consequences

- `tools/scaffold-engine.py` must keep every new engine's top-level package
  name added to this contract's `forbidden_modules` list, exactly as it
  already does for the other five import-linter contracts (the four from
  Phase 0-2D plus ADR-033's).
- Any future addition to `nova-service-kit` (or a future shared package this
  ADR governs) that appears to need engine-specific knowledge is a signal
  that addition does not belong in a shared package at all — it belongs in
  the one engine that needs it, kept duplicated if a second engine ever needs
  something similar but not identical (exactly the judgment call the
  boilerplate extraction proposal's evaluation framework, §3, already applies
  per-pattern).
- Reviewers of any future PR touching `nova-service-kit` should treat a new
  parameter or conditional branch as a request to justify against this ADR,
  not a routine addition.

## Tradeoffs

- A strict zero-engine-specific-knowledge rule means some future duplication
  will remain duplication rather than being folded into `nova-service-kit`,
  even where doing so might look convenient in the moment. Accepted: this is
  the same tradeoff the boilerplate extraction proposal already made
  explicitly for `Goal`, `HumanOverrideRequest`, and every narrow ID+summary
  cross-engine value object (`docs/design/nova-service-kit/
  boilerplate-extraction-proposal.md` §6-7) — genuine architectural
  boundaries are worth more than a marginally smaller line count.
- One more import-linter contract for `tools/scaffold-engine.py` to keep
  populated. Accepted: proven low-maintenance mechanism already in place for
  five other contracts.

## Future implications

- If a future shared infrastructure package's own scope statement turns out
  to need a genuine exception to this rule, that is a new architectural
  decision requiring its own ADR amendment — this ADR does not pre-authorize
  exceptions.
- This ADR does not apply to `nova_contracts`, which is deliberately the
  *shared vocabulary* layer every engine depends on and is expected to
  contain types shaped by (though not naming) engine-specific concepts (per
  Extraction E of the boilerplate extraction proposal, deferred and separately
  gated, not part of this ADR's own subject matter).

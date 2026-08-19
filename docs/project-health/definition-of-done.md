# Phase / Sub-Phase Definition of Done

**Status: permanent, standing project policy**, established 2026-08-18 during the
Phase 3D documentation and project-state synchronization pass, generalized from the
documentation discipline that pass required of Phase 3D specifically. Applies to
every future Phase and Sub-Phase, not just Phase 3D.

This is a phase-level completion checklist. It does not duplicate or replace two
existing, narrower policies it builds on:

- [`docs/project-health/README.md`](README.md) already establishes the rule that
  **a phase is not fully closed until both its Gate Review and its Project Health
  record exist** — that rule is restated here as items 1-2 below, not re-derived.
- [`docs/architecture/15-development-workflow.md` §4](../architecture/15-development-workflow.md#4-definition-of-done-per-pr)
  ("Definition of Done (per PR)") and
  [§8](../architecture/15-development-workflow.md#8-the-permanent-subsystem-lifecycle)
  ("The permanent subsystem lifecycle") already establish a broader, PR-level and
  subsystem-lifecycle Definition of Done (tests, contract updates, API
  compatibility, architecture documentation, sequence/component diagrams,
  observability, and more) — this document does not restate that checklist either.
  Every item there still applies; this document adds the phase-level items that sit
  *above* individual PRs: the record-keeping a phase's own closure requires once its
  PR(s) already satisfy §4/§8.

Read this document alongside those two, not instead of them.

## The checklist

A Phase or Sub-Phase is not considered fully closed until all of the following
exist:

1. **Gate Review** — a document under `docs/roadmap/architecture-reviews/`,
   following this project's established Gate Review structure (scope executed,
   architectural decisions implemented, contracts added, persistence, testing and
   verification results, known limitations, forward/backward phase-contamination
   checks, acceptance criteria, final gate status). See any Phase 3 Gate Review
   (`phase-3a-gate-review.md`, `phase-3b-domain-foundation-gate-review.md`,
   `phase-3b-decomposition-orchestration-gate-review.md`,
   `phase-3c-capability-engine-gate-review.md`,
   `phase-3d-action-engine-gate-review.md`) for the current reference shape.
2. **Project Health record** — a `docs/project-health/phase-N.md` snapshot (the
   standardized 23-field shape `docs/project-health/README.md` defines) and a
   corresponding row in `docs/project-health/project-health-master.md`'s master
   timeline. Per `docs/project-health/README.md`: a phase is not fully closed until
   both this and item 1 exist.
3. **TDD / design / implementation documentation currency** — the phase's own TDD
   or design document (`docs/design/phase-N/...`) accurately reflects what was
   actually implemented. Where implementation diverged from the original design, or
   where a later research/decision pass changed something the TDD itself still
   describes differently, the TDD is corrected — additively, per item 6 below, not
   silently rewritten.
4. **Engineering roadmap / status update** — `docs/roadmap/ENGINEERING_ROADMAP.md`'s
   entry for the phase reflects its actual current status (complete/in
   progress/blocked, merged/not yet merged, acceptance-criteria status), not merely
   its original planning-stage description.
5. **README / current project status** — where the phase changes what a reader of
   the top-level `README.md` would reasonably expect to be told (a new phase
   completed, the canonical branch changed, a new engine now exists), the README's
   own Status section is updated. Per this project's own standing constraint: this
   is a minimal, targeted edit — never a rewrite of unrelated README content.
6. **Reconciliation / correction notes for historical documentation** — where
   closing a phase requires correcting an earlier document (a stale claim, a
   superseded characterization, a since-resolved fork), the correction is additive:
   the original text is preserved, and a dated note explains what changed and why.
   Historical documents are never silently rewritten to read as though they always
   said the corrected thing.
7. **Tests and verification evidence** — the phase's own test suite (unit,
   contract, integration) is documented in the Gate Review and Project Health
   record with actual pass/fail counts and coverage figures, not asserted without
   evidence.
8. **CI, Trivy, and real-infrastructure verification, where applicable** — real
   GitHub Actions CI results (not merely local verification) are cited with the
   exact commit SHA they were confirmed against. Where the phase touches a
   Dockerfile, Trivy scan results are recorded. Where the phase touches persistence,
   real-infrastructure (real Postgres/Neo4j/Redis/NATS, not fakes) verification is
   recorded, or its absence is explicitly disclosed as a known gap — never silently
   omitted.
9. **Final acceptance-criteria status** — the phase's own acceptance criteria (from
   its TDD, its research/decision documents, or both) are enumerated with an
   explicit met/not-met status each, in the Gate Review. A phase is not described as
   complete while a required acceptance criterion is unmet without that gap being
   explicitly flagged, not glossed over.
10. **Final merge-readiness review** — before a phase's PR(s) are merged, an
    explicit merge-readiness check confirms: the exact head SHA, CI status against
    that exact SHA, a clean working tree, and that the diff contains only the
    intended changes (documentation-only PRs contain no application-code changes;
    implementation PRs contain no undisclosed scope creep).

## What "not fully closed" means in practice

A phase can be *implemented* and *CI-green* without being *closed* — Phase 3D's own
history is the concrete example this document generalizes from: its implementation
PR (#13) reached 22/22 green CI before its Gate Review, Project Health record, and
acceptance-criteria accounting existed, and reaching "all 7 acceptance criteria met"
still required a dedicated documentation and closure pass after the code itself was
already correct. Green CI on an implementation PR is necessary but not sufficient
for a phase to be considered done — the ten items above are the remaining,
mandatory work, and per standing instruction, none of them authorizes starting the
next phase on their own; that always requires the user's separate, explicit
approval.

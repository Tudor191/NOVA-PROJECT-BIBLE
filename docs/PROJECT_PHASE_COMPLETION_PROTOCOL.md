# NOVA Project — Phase & Slice Completion Protocol

**Status: permanent, standing, mandatory project policy.** Established 2026-08-29.
Applies to every Phase, Sub-Phase, and significant Slice from this date forward,
and to every retrospective closure of an earlier one.

---

## 0. The standing rule

> **Before every Gate Review, every Phase or Sub-Phase completion, every Slice
> completion report, and every final Phase report, the agent MUST read this
> entire document and execute every category in it.**
>
> The user does not need to restate these requirements. Their absence from a
> given instruction is **not** permission to skip them. An instruction that says
> only "complete Phase N" or "write the Gate Review" is a full invocation of this
> protocol.

Two corollaries that are part of the rule, not commentary on it:

- **Executing this protocol is never self-authorization to start the next Phase
  or Slice.** Completing a phase and beginning the next are two separate
  decisions, and the second is always the user's, explicitly.
- **A category that does not apply must be reported as "N/A" with the reason**,
  never silently omitted. Fifteen categories go into every report; some of them
  may be one line long.

### 0.1 Scope — what triggers this protocol

| Unit | Trigger | Depth |
|---|---|---|
| **Phase** (e.g. Phase 3) | Declaring the phase complete; writing its Gate Review; final phase report | Full protocol, all 15 categories |
| **Sub-Phase** (e.g. Phase 3E) | Same as Phase | Full protocol, all 15 categories |
| **Significant Slice** (a separately-reviewable unit inside a Sub-Phase — e.g. "Slice 2: real parallel dispatch") | Declaring the slice complete; any slice completion report | Categories 1, 2, 8, 9, 10, 11, 13, 14 in full; categories 3–7 and 12 as a **deferred-obligations ledger** (see §0.2) |
| **Any PR** | Opening or merging | [SAD 15 §4](architecture/15-development-workflow.md#4-definition-of-done-per-pr) per-PR Definition of Done, plus categories 8, 9, 11 |

A "significant Slice" is any unit the user has named as a slice, milestone, or
separately-approved step, or any unit whose completion the agent intends to
report as done. When in doubt, treat it as significant.

### 0.2 The deferred-obligations ledger (Slices)

A Slice does not get to skip categories 3–7 and 12 — it gets to **defer** them,
in writing. Every Slice completion report must end with a ledger of what the
Slice has made stale or newly required but has not yet updated, so the
Sub-Phase's eventual Gate Review inherits a complete list rather than
rediscovering it. Each ledger row names the document, what changed about it, and
which Phase/Sub-Phase closure will settle it.

**A Sub-Phase may not be declared complete while any ledger row from any of its
Slices is unsettled.**

### 0.3 Core principles

These govern how every category below is executed.

1. **Repository-driven, always.** Never assume any document is current. Every
   claim in a Gate Review, Project Health record, roadmap entry, or completion
   report must be traceable to an inspection performed *in this session* against
   *the actual repository at a named commit* — a file read, a command run, a
   grep executed. "The TDD says X" is not evidence that X was built; "the
   previous Gate Review said Y" is not evidence that Y is still true.
2. **Documentation is presumed stale until inspected.** The burden of proof runs
   toward staleness, not away from it. A document that has not been opened during
   this protocol run has not been verified, and must be reported as unverified
   rather than assumed fine.
3. **Evidence, not assertion.** Every pass/fail claim carries the command that
   produced it and the output that proves it — counts, coverage percentages,
   commit SHAs, CI run conclusions. "Tests pass" without numbers is not a
   verification result.
4. **Corrections are additive.** When closing a phase requires fixing an earlier
   document, preserve the original text and add a dated note explaining what
   changed and why. Historical documents are never silently rewritten to read as
   though they always said the corrected thing. (This is
   [`project-health/definition-of-done.md`](project-health/definition-of-done.md)
   item 6, restated because it governs categories 5, 6, 7, 12, and 14 here.)
5. **Report the gap rather than close it by assumption.** Where verification is
   impossible in the current environment (no Docker daemon, no CI access, an
   external dependency down), say so explicitly and name what remains unverified.
   Never let an unrunnable check silently become a passed check.
6. **Never narrow scope unilaterally.** If part of a phase's approved scope was
   not built, the phase is not complete. Report the shortfall; do not redefine
   the phase to fit what exists.

### 0.4 Order of execution

Run the categories in this order. Later categories depend on earlier findings.

```
1  Implementation vs TDDs/ADRs/decisions   ─┐
2  Acceptance criteria                      ├─ establish ground truth
8  Contracts + codegen                      │
9  Tests / lint / types / imports / CI      │
10 Real-infrastructure                      │
11 PR / branch / commit / CI evidence      ─┘
        ↓
6  docs/ staleness sweep                   ─┐
7  READMEs + public docs                    ├─ reconcile documentation
12 Cross-file consistency                   │
14 Documentation updates                    │
5  Roadmap                                 ─┘
        ↓
4  Project Health record
3  Gate Review + Go / Conditional-Go / No-Go
13 Gaps, ambiguities, decisions for approval
15 Mandatory final checklist
```

Category 13 is written last but **collects findings from every prior category**;
anything that surfaced an ambiguity anywhere goes there.

---

## 1. Verification of implementation against TDDs, ADRs, and approved architectural decisions

### 1.1 What must be checked

- **Every claim the phase's own TDD makes about what would be built** — module
  by module, event by event, endpoint by endpoint, table by table — checked
  against the actual source, not against the commit messages that claim to have
  implemented it.
- **Every ADR the phase touches**, in both directions: the implementation obeys
  the ADR, *and* the implementation has not made the ADR obsolete or false. An
  ADR that the code has quietly outgrown is a finding.
- **Every architectural decision the user approved in-session** (fork
  resolutions, option choices, explicitly approved designs — e.g. "Option B",
  "Option C hand-off ordering"): each is re-read and checked against what the
  code actually does now. Decisions approved in an earlier session are as binding
  as decisions approved in this one.
- **Every deviation from the TDD**, whether deliberate (an approved narrowing) or
  accidental (drift). Each must be classified: *approved*, *disclosed narrowing*,
  *undisclosed drift*, or *defect*.
- **Ownership and boundary constraints** — which engine owns which state, which
  engine may write which table, which engine may import which package. Verified
  against the ADRs and against `uv run lint-imports`, not against intent.
- **Every "correction" or "reconciliation note"** the phase added to a design
  document: does it accurately describe the code as it now stands?
- **Docstrings and code comments that cite documents.** A docstring asserting
  "doc 12 §15 defers this" is a claim about a document; open the document and
  verify it. Citations inside source code are documentation and are covered by
  this protocol. (This is not hypothetical: a false citation of exactly this kind
  was found and corrected in `agent-os/kernel/domain/scheduler.py` during Phase
  3E.)

### 1.2 Which files and repository areas must be inspected

| Area | Path | What to look for |
|---|---|---|
| Phase TDD / design docs | `docs/design/phase-<N>/` | Every section describing what would be built |
| ADRs | `docs/architecture/adr/` (currently 24 ADRs + `README.md`) | Every ADR the phase's engines/packages touch |
| Canonical architecture | `docs/architecture/00`–`23`, especially `00-overview-and-decisions.md`, `12-agent-architecture.md`, `20-engine-responsibility-boundaries.md`, `07-database-architecture.md`, `09-event-bus-architecture.md`, `10-inter-engine-communication.md` | Claims about the subsystem the phase changed |
| Bible | `docs/bible/part-01`–`part-20` | The Part(s) the phase implements — SAD 15 §4 item 5 requires PRs to cite them |
| Implementation | `services/<engine>/src/`, `agent-os/<component>/src/`, `agents/<agent>/`, `packages/<pkg>/src/`, `tools/` | The actual code |
| Boundary config | `pyproject.toml` `[tool.importlinter]` (7 contracts, `root_packages`) | New modules registered; contracts still accurate |
| Prior approvals | This session's transcript and any decision document under `docs/design/phase-<N>/` | Every option the user chose |

### 1.3 What must be updated

- The phase's own TDD/design doc, **additively**, wherever implementation
  diverged from design or a later decision superseded the original text.
- Any ADR whose statement the implementation has falsified — either the code is
  wrong (fix the code) or the ADR is superseded (write a new ADR; do not edit the
  old one's decision in place).
- Any source docstring or comment carrying a citation that inspection proved
  false.
- `pyproject.toml`'s `[tool.importlinter]` `root_packages` and contract `modules`
  lists, if the phase added a package, engine, or `agent-os` component.

### 1.4 What must be reported

1. A **TDD conformance table**: every TDD requirement → *implemented as
   specified* / *implemented with disclosed deviation* / *not implemented* /
   *superseded by approved decision*, each with a file:line citation.
2. An **ADR conformance statement** naming each ADR checked and its verdict.
3. An **approved-decisions table**: each user-approved decision → where it is
   implemented (file:line) → verified/not.
4. A **deviation register**: every divergence, classified per §1.1, with the
   approval that authorizes it or an explicit note that none exists.
5. Every **false or unverifiable citation** found in source or documentation.

---

## 2. Verification of every acceptance criterion

### 2.1 What must be checked

- **Every acceptance criterion, enumerated individually and numbered.** Sources:
  the phase's TDD acceptance-criteria section, its research/decision documents,
  `docs/roadmap/ENGINEERING_ROADMAP.md`'s entry for the phase, and any criterion
  the user stated in-session. All four sources must be consulted — criteria in
  this project have historically lived in more than one place.
- For each criterion: **the specific test, command output, or file:line that
  proves it**, executed in this session. A criterion "met" by reasoning rather
  than by evidence is not met.
- **Criteria whose wording is binding and must not be softened.** Where a
  criterion says "a real X", "end-to-end", "a real git commit", or similar, the
  literal reading governs. Descoping a criterion requires the user's explicit
  approval, recorded; it is never the agent's call.
- **Partially met criteria.** These are *not met*. A criterion is binary; the
  partial progress is described in the notes, not in the verdict.

### 2.2 Which files and repository areas must be inspected

- `docs/design/phase-<N>/` — the TDD's own acceptance-criteria section, plus any
  criteria embedded in research or decision documents.
- `docs/roadmap/ENGINEERING_ROADMAP.md` — the phase entry's own stated criteria.
- The tests that prove each criterion: `services/*/tests/`, `agent-os/*/tests/`,
  `agents/*/tests/`, `packages/*/tests/`, `tools/tests/`.
- Prior Gate Reviews under `docs/roadmap/architecture-reviews/`, for criteria
  carried forward or previously reported unmet.

### 2.3 What must be updated

- The Gate Review's acceptance-criteria section (category 3).
- The roadmap entry's criteria status (category 5).
- The Project Health record's acceptance-criteria field (category 4).
- Where a criterion was **found unmet after having previously been reported
  met**, an additive correction note in the document that made the earlier claim.

### 2.4 What must be reported

A single table, no criterion omitted:

| # | Criterion (verbatim) | Source doc §  | Status | Evidence (test name / file:line / command output) |
|---|---|---|---|---|

Statuses: **Met** / **Not met** / **Met with disclosed narrowing (approval cited)** /
**Deferred by approval (approval cited)** / **Cannot be verified in this
environment (reason)**.

Followed by an explicit sentence: *"N of M acceptance criteria are met. The
unmet criteria are: …"* — or *"All M acceptance criteria are met."* Never a
phase declared complete with an unmet criterion unless the gap is stated in that
same sentence.

---

## 3. Gate Review and Go / Conditional-Go / No-Go criteria

### 3.1 What must be checked

- Whether a Gate Review document exists for this phase at
  `docs/roadmap/architecture-reviews/phase-<N>-<slug>-gate-review.md`.
- Whether it follows this project's established Gate Review structure. The
  canonical shape is
  [`docs/roadmap/architecture-reviews/TEMPLATE.md`](roadmap/architecture-reviews/TEMPLATE.md)
  (§1 what was implemented, §2 why each architectural decision was made, §3
  tradeoffs considered, §4 known limitations, §5 technical debt introduced, §6
  future improvements, §7 risks, §8 compatibility with the NOVA Project Bible,
  Sign-off); recent Phase 3 Gate Reviews extend it with scope executed, contracts
  added, persistence, verification results, forward/backward phase-contamination
  checks, and acceptance criteria. Use the most recent Phase 3 Gate Review as the
  working reference shape.
- Whether the **Project Metrics** section required by
  [SAD 15 §10](architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate)
  is present, in the shape
  [`METRICS_TEMPLATE.md`](roadmap/architecture-reviews/METRICS_TEMPLATE.md)
  defines (Project Statistics, Implementation Statistics, Language Breakdown,
  Architecture Metrics, Quality Metrics, Growth Metrics, Complexity Metrics).
  **This requirement has silently degraded before in this project's history** —
  that is precisely why `docs/project-health/` exists. Check it explicitly, every
  time.
- Whether the **SLOC milestone thresholds** have been crossed: the **~30,000
  Production SLOC reminder** (surface a Project Health Review recommendation to
  the user; a reminder, not a pause) and the **~50,000 Production SLOC gate**
  (feature development pauses automatically pending an Engineering Review
  Milestone). Production SLOC = `src/` application code + Alembic migrations,
  excluding blanks, comments, tests, generated code, and documentation.
- Whether the phase's **forward and backward contamination checks** were done: no
  work from a later phase leaked into this one, and no work this phase owed was
  pushed silently into a later one.
- **Every one of the ten items in
  [`docs/project-health/definition-of-done.md`](project-health/definition-of-done.md)**,
  which this protocol subsumes and does not replace.

### 3.2 The gate decision

The Gate Review must end with exactly one of three verdicts, stated explicitly.

**GO** — all of the following hold:

1. Every acceptance criterion is **Met** (category 2), or narrowed/deferred with
   a cited user approval.
2. No undisclosed deviation from TDD, ADR, or approved decision (category 1).
3. `pnpm turbo run lint` and `pnpm turbo run test --force` both pass repo-wide,
   with real counts recorded (category 9).
4. Every affected package meets the 85% domain-coverage gate (category 9).
5. `uv run lint-imports` reports 0 broken contracts (category 9).
6. Contract and codegen verification clean — zero unexplained drift (category 8).
7. Real GitHub Actions CI green against the exact head SHA (category 11).
8. Real-infrastructure verification either passed or its absence explicitly
   disclosed as a named, scoped gap (category 10).
9. Gate Review, Project Health record, roadmap entry, and README status all exist
   and are current (categories 3–5, 7).
10. No document in the repository contradicts the repository's current state
    (category 12).
11. No open item in category 13 requires a user decision before the phase can be
    called done.

**CONDITIONAL-GO** — the phase is substantively complete, but one or more of the
following is true. Each condition must be listed individually, with an owner and
the specific event that discharges it:

- A real-infrastructure suite could not be executed locally and has not yet run
  in CI (the standard condition in this project's environment — see category 10).
- A non-blocking CI workflow (`real-infra-checks.yml` is non-blocking by design)
  has not yet reported.
- A known limitation is documented and accepted, and does not affect an
  acceptance criterion.
- A documentation update is queued but depends on a merge that has not happened.

CONDITIONAL-GO is **not** a way to pass a phase with an unmet acceptance
criterion. An unmet criterion is a NO-GO unless the user has explicitly approved
deferring it.

**NO-GO** — any of:

- An acceptance criterion is unmet without approval.
- An undisclosed deviation from an approved architectural decision exists.
- Any blocking gate is red: lint, mypy, tests, coverage, import-linter, contract
  drift, or required CI.
- A document contradicts the repository state and has not been corrected.
- An architectural ambiguity was found that requires a user decision and has not
  been resolved (category 13).
- The phase's scope was silently narrowed.

### 3.3 What must be updated

- Create or complete the Gate Review document at
  `docs/roadmap/architecture-reviews/phase-<N>-<slug>-gate-review.md`.
- Never retroactively edit a *previous* phase's Gate Review to fit today's
  format. If a previous Gate Review contains a claim now known false, add a dated
  correction note (principle 0.3.4) rather than rewriting it.

### 3.4 What must be reported

- The verdict — **GO**, **CONDITIONAL-GO**, or **NO-GO** — stated in those words.
- For CONDITIONAL-GO: the numbered condition list, each with its discharge event.
- For NO-GO: exactly what is blocking, and what would clear it.
- The Project Metrics section, including the current Production SLOC figure, the
  tool and flags used (`cloc` or `scc`, with flags), the scope counted, and
  whether either SLOC milestone was crossed.
- Confirmation that all ten `definition-of-done.md` items were checked, item by
  item.

---

## 4. Project Health and health-tracking documents

### 4.1 What must be checked

- Whether `docs/project-health/phase-<N>.md` exists for this phase.
- Whether it uses the **standardized 23-field shape** that
  [`docs/project-health/README.md`](project-health/README.md) defines: phase
  identity, date, branch, PR, commit, status, SLOC ×4, tests ×2, coverage, CI,
  real-infrastructure, documentation health, architecture status, security
  status, unverified infrastructure, open blockers, branch hygiene, notes.
- Whether **every value is cited back to its source** — normally a specific
  section or line of that phase's own Gate Review.
- Whether `docs/project-health/project-health-master.md`'s summary table has a
  row for this phase, and whether its §2 SLOC-methodology history needs a new
  entry (required if the tool or scope changed).
- Whether any field is genuinely unavailable. If so it reads **"Not reported"**
  or **"Not measured"** — never blank, never inferred, never backfilled from
  today's repository state, never averaged from an adjacent phase.
- Whether two SLOC figures being compared used the **same tool and same scope**.
  If not, they are recorded side by side with an explicit incomparability label,
  never merged into one trend.
- For a phase that shipped as **multiple separately-reviewed units** (Phase 3B is
  the precedent), whether the health file keeps them as separated sub-sections
  rather than merging their numbers.

### 4.2 Which files must be inspected

- `docs/project-health/README.md` — the field definitions and the rules above.
- `docs/project-health/definition-of-done.md` — the ten-item checklist.
- `docs/project-health/project-health-master.md` — the master timeline and §2
  methodology history.
- `docs/project-health/phase-*.md` — the prior records, for shape and for trend
  continuity.
- This phase's own Gate Review — the source every field cites.

### 4.3 What must be updated

- Create `docs/project-health/phase-<N>.md` (or extend it, for a multi-unit
  phase).
- Add or update this phase's row in `project-health-master.md`'s summary table.
- Add a §2 methodology entry if the SLOC tool or scope changed.
- Where a previously-recorded value is now known to be wrong, add a dated
  correction — never silently overwrite a historical figure.

### 4.4 What must be reported

- Confirmation that both the Gate Review **and** the Project Health record exist
  — per `project-health/README.md`, a phase is not closed until both do.
- The 23 fields as filled, with every "Not reported" called out explicitly and
  the reason it is unavailable.
- Whether the SLOC series remained comparable to the previous phase, and if not,
  why.

---

## 5. ENGINEERING_ROADMAP.md and other roadmap documents

### 5.1 What must be checked

- `docs/roadmap/ENGINEERING_ROADMAP.md`'s entry for this phase: does it state the
  phase's **actual current status** — complete / in progress / blocked, merged /
  not yet merged, acceptance-criteria status — rather than its original
  planning-stage description?
- Whether the entry's **acceptance criteria** still match the criteria actually
  used in category 2. Where they diverge, which is authoritative must be stated,
  not left ambiguous.
- Whether the roadmap's description of **what the phase would build** still
  matches what it did build. Deliverables added, dropped, or moved to a later
  phase must be reflected.
- Whether **downstream phase entries** need adjusting: a phase that absorbed work
  from Phase N+1, or deferred work into it, changes that entry too.
- The roadmap's **"How this roadmap is organized"** preamble and
  **"Cross-phase notes"** section, for statements the phase falsified.
- Whether any **other roadmap-shaped document** carries a phase-status claim:
  `docs/roadmap/architecture-reviews/project-health-review-2026-08.md`, the phase
  master-scope documents under `docs/design/phase-<N>/` (e.g.
  `02-master-scope.md`), and `docs/project-health/project-health-master.md`.

### 5.2 Which files must be inspected

- `docs/roadmap/ENGINEERING_ROADMAP.md` — the whole phase entry, plus the
  preamble and cross-phase notes.
- `docs/roadmap/architecture-reviews/` — all prior Gate Reviews making
  forward-looking claims about this phase.
- `docs/design/phase-<N>/` — master-scope and research documents stating phase
  boundaries.
- `docs/project-health/project-health-master.md`.

### 5.3 What must be updated

- The roadmap entry's status line, acceptance-criteria status, and deliverable
  list.
- Adjacent phase entries whose scope this phase changed.
- Cross-phase notes falsified by this phase.

All roadmap edits are **targeted**: change the statements the phase actually
affects. Do not rewrite unrelated roadmap content.

### 5.4 What must be reported

- The exact roadmap text before and after, for each edit.
- Any place the roadmap and the TDD state **different** acceptance criteria for
  the same phase, and which was treated as authoritative.
- Any downstream phase whose scope this phase changed, and how.

---

## 6. Staleness sweep of every document under `docs/`

### 6.1 What must be checked

This is the category most often skipped and most often wrong. It is a **sweep**,
not a spot-check: every document that could have been falsified by the
implementation must be opened, not merely considered.

Check, at minimum:

- **Architecture documents** (`docs/architecture/00`–`23`) — any that describe a
  subsystem the phase touched. Highest-risk in this project:
  - `00-overview-and-decisions.md` (ADR index and canonical decisions)
  - `02-repository-and-folder-structure.md` (new packages, engines, `agent-os`
    components, agents)
  - `07-database-architecture.md` (new tables, schemas, migrations)
  - `09-event-bus-architecture.md` and `10-inter-engine-communication.md` (new
    subjects, RPCs, publishers, subscribers)
  - `11-api-architecture.md` (new endpoints, OpenAPI, backward compatibility)
  - `12-agent-architecture.md` (NAOS: kernel, registry, supervisors, agent
    packages — including §15's "what ships in Phase 3 vs. what the architecture
    already supports" table, which becomes stale as Phase 3 ships)
  - `15-development-workflow.md` (§4 DoD, §8 lifecycle, §9 deliverable checklist,
    §10 metrics)
  - `16-testing-strategy.md` (test tiers, coverage gate, real-infra policy)
  - `17-cicd-pipeline.md` (workflow names, jobs, gates)
  - `20-engine-responsibility-boundaries.md` (ownership changes)
- **ADRs** (`docs/architecture/adr/`) — any whose decision the phase implemented,
  changed, or falsified; plus `adr/README.md`'s index if an ADR was added.
- **Bible parts** (`docs/bible/part-01`–`part-20`) — the Bible is the source
  specification and is **not** edited to match implementation drift. What is
  checked here is the reverse: whether the implementation still satisfies the
  Part, and whether any Gate Review claim of Bible compatibility is still true.
  A genuine Bible correction requires the user's explicit approval.
- **Design documents** (`docs/design/`) — this phase's own package
  (`phase-<N>/`), plus earlier phases' documents describing behavior this phase
  changed, plus `docs/design/nova-service-kit/` and `docs/design/nova-testkit/`
  if shared infrastructure changed.
- **Prior Gate Reviews** (`docs/roadmap/architecture-reviews/`) — for
  forward-looking claims ("this will be addressed in Phase N+1", "deferred to
  the Kernel slice") that this phase has now settled or falsified.
- **Phase design-package READMEs** — `docs/design/phase-1/README.md` through
  `docs/design/phase-2d/README.md`. **Note a live gap:** `docs/design/phase-3/`
  currently has no `README.md`, unlike every earlier phase package. Closing
  Phase 3 should either add one or record the deliberate decision not to.
- **`docs/project-health/`** and **`docs/roadmap/`** — covered by categories 4
  and 5, re-checked here for cross-references.

### 6.2 How to sweep (mechanically, not by memory)

Run targeted searches for the terms the phase made stale, and open every hit:

```bash
# Names the phase introduced, renamed, or removed
grep -rn "<old-class-name>\|<old-event-subject>\|<removed-module>" docs/

# Forward-looking claims this phase may have settled
grep -rniE "not yet (implemented|shipped|built)|deferred to|will be (added|addressed)|planned for phase|future phase|TODO|not currently" docs/

# Phase-status claims anywhere in docs
grep -rniE "phase [0-9][a-z]? (is |was )?(complete|in progress|not started|merged)" docs/

# Counts that drift: engines, packages, agents, ADRs, contracts
grep -rniE "(thirteen|fourteen|fifteen|[0-9]+) (engines|packages|agents|ADRs|contracts)" docs/
```

Then reconcile each numeric claim against the repository:

```bash
ls -1d services/*/ agent-os/*/ agents/*/ packages/*/ | wc -l   # subsystem counts
ls -1 docs/architecture/adr/ADR-*.md | wc -l                    # ADR count
uv run lint-imports 2>&1 | tail -2                              # contract count
```

### 6.3 What must be updated

Every document the sweep proves stale, corrected **additively** where it is a
historical record (Gate Reviews, prior phase documents) and **directly** where it
is a living reference (architecture docs, READMEs, roadmap).

### 6.4 What must be reported

- The **exact grep commands run** and how many hits each produced.
- A table: document → stale claim (verbatim) → correction made → or *why no
  correction was needed*.
- An explicit list of documents inspected and found **already accurate** — this
  is evidence the sweep was real, not selective.
- Any document the sweep could not resolve, escalated to category 13.

---

## 7. READMEs and other public documentation

### 7.1 What must be checked

- **Top-level `README.md`** — its `## Status` section. This project's README
  carries specific, falsifiable claims: which phases are implemented and merged,
  how many engines exist, the canonical branch, merge commits and PR numbers.
  Every such claim is checked against the repository. (The README's Phase status
  line has gone stale before and required a dedicated fix; treat it as
  high-risk.)
- **Every subsystem README** the phase touched:
  - `services/<engine>/README.md` (14 engines)
  - `agent-os/kernel/README.md`, `agent-os/registry/README.md`,
    `agent-os/supervisors/README.md`, `agent-os/sdk/python/README.md`
  - `agents/<agent>/README.md` (5 agent packages)
  - `packages/<pkg>/README.md` (8 shared packages)
  - `infra/docker/README.md`
- Each such README's description of its own **public surface** — endpoints,
  published/subscribed events, RPC subjects, configuration, known gaps.
- **Known-gap sections.** A README claiming a gap the phase closed is as stale as
  one claiming a feature that does not exist. Both directions must be checked.
- **Documentation index READMEs**: `docs/architecture/README.md`,
  `docs/architecture/adr/README.md`, `docs/bible/README.md`,
  `docs/project-health/README.md`, and the per-phase design READMEs — do they
  list documents the phase added?

### 7.2 What must be updated

- The top-level README's Status section — a **minimal, targeted edit**. Never a
  rewrite of unrelated README content.
- Subsystem READMEs for any changed public surface or resolved/introduced gap.
- Index READMEs, where the phase added a document they should list.

### 7.3 What must be reported

- Every README inspected, with a verdict: *updated* / *checked, already accurate*
  / *N/A, untouched by this phase*.
- The exact before/after text of each README edit.
- Any known-gap claim that the phase resolved, with the README line that used to
  assert it.

---

## 8. Contract verification and codegen verification

### 8.1 What must be checked

- Whether the phase changed `packages/nova-contracts/` at all. Determine this
  from the diff, not from memory:
  ```bash
  git diff --stat <base>..HEAD -- packages/nova-contracts/
  ```
- If contracts changed:
  - Every new or changed payload has a **contract test** under
    `packages/nova-contracts/tests/`.
  - Every **consumer** of the changed payload still validates — locate consumers
    by grepping for the payload class name across `services/`, `agent-os/`,
    `agents/`, and `packages/`.
  - The change is **additive** where consumers are already deployed; a
    field-required or field-removed change is a breaking change and must be
    called out explicitly (SAD 15 §4 item 3;
    [`11-api-architecture.md` §6](architecture/11-api-architecture.md#6-backward-compatibility--deprecation-policy)).
  - `schema_version` handling is correct for the payload family.
- **TypeScript codegen drift, in every case** — whether or not contracts changed.
  Regenerate and confirm the working tree is clean afterward:
  ```bash
  uv run python packages/nova-contracts/codegen/generate_typescript.py
  git status --short packages/nova-contracts
  ```
  Empty output = zero drift. Non-empty output = the committed TypeScript does not
  match the Python source and must be committed or explained. Running this when
  contracts were *not* changed is not wasted work: a clean result is the positive
  evidence that the phase left contracts untouched.
- **Event-subject registration** — a new subject must be registered wherever
  `nova_eventbus_sdk` requires it, and each engine's `publishable_subjects` /
  `subscribable_subjects` sets must match what it actually publishes and
  subscribes to.
- **OpenAPI / REST surface** — if an engine's public API changed, the diff is
  reviewed for backward compatibility per SAD 15 §4 item 4.

### 8.2 Which files and areas must be inspected

- `packages/nova-contracts/src/` — the payload definitions.
- `packages/nova-contracts/tests/` — the 12 contract-test modules
  (`test_envelope.py`, `test_agent_os_events.py`, `test_planning_events.py`, …).
- `packages/nova-contracts/codegen/generate_typescript.py` and
  `packages/nova-contracts/typescript/` (the generator currently reports 97
  contract files; the directory holds 98 `.ts` files, the extra being the
  `index.ts` barrel it also writes but does not count in that message).
- Every consumer found by grep.
- `packages/nova-eventbus-sdk/src/` — subject registration.

### 8.3 What must be updated

- Contract tests for every new or changed payload.
- Regenerated TypeScript, committed in the same change as the Python contract.
- Consumers requiring updates for a changed contract.
- `docs/architecture/09-event-bus-architecture.md` and
  `10-inter-engine-communication.md` for new subjects or RPCs.

### 8.4 What must be reported

- Whether `packages/nova-contracts/` changed — with the `git diff --stat` output
  as evidence, including the negative case.
- Codegen result: the file count regenerated and the `git status` output proving
  zero drift.
- For each changed payload: its consumers, and each consumer's verification
  status.
- Any breaking change, called out explicitly as breaking, with its migration
  story.

---

## 9. Tests, coverage, lint, mypy, import-linter, and CI

### 9.1 The commands — run these exactly

These are this repository's real gates, verified against `package.json`,
`turbo.json`, `pyproject.toml`, and `.github/workflows/`. Run all of them.

```bash
# Lint + type-check, every package (per-package: ruff check . && mypy src)
pnpm turbo run lint

# Tests, every package, UNCACHED
pnpm turbo run test --force

# Import boundaries (ADR-004/006/007/020/033/034 + nova-agent-sdk): 7 contracts
uv run lint-imports

# Scaffolding tools (not a workspace package — CI runs this separately)
uv run pytest tools/tests -q

# docker-compose validity
docker compose -f infra/docker/docker-compose.local.yml config --quiet

# Contract codegen drift (see category 8)
uv run python packages/nova-contracts/codegen/generate_typescript.py && git status --short packages/nova-contracts

# Per affected package, for the coverage figure
uv run --package <pkg> pytest -m "not real_infra" --cov=<module>.domain
```

**`--force` is mandatory for the test run.** Turborepo caches task results; a
"26/26 successful" line with `Cached: 24` did not execute those 24 suites. A
Gate Review may only cite an uncached run.

### 9.2 What must be checked

- **Lint**: `ruff check` clean for every package. Note: **`ruff format` is not a
  gate** in this repository — neither `package.json`'s `lint` script nor
  `.github/workflows/pr-checks.yml` runs it, and a large pre-existing formatting
  baseline exists. Do not report `ruff format --check` output as a failure, and
  do not reformat unrelated files to "fix" it.
- **Types**: `mypy src` clean for every package, with the source-file count
  recorded.
- **Tests**: real pass / fail / deselected counts per package, from the uncached
  run.
- **Coverage**: the **85% domain-coverage gate** (`[tool.coverage.report]`
  `fail_under = 85`, `branch = true`, centralized in `pyproject.toml` per
  ADR-033) for every affected package. Record the actual percentage, not just
  "passed".
- **Import boundaries**: `uv run lint-imports` — the expected result is
  *"Contracts: 7 kept, 0 broken."* If the contract count changed, say why.
- **New tests actually test something.** For any test asserting a concurrency,
  ordering, isolation, or timing property, **prove the test fails when the
  property is removed** — temporarily revert the implementation, observe the
  failure, restore, re-confirm. A test that passes against both the correct and
  the broken implementation is not evidence. Report the negative-control result.
- **Flakiness**, for any test involving timing, async scheduling, or I/O: run it
  repeatedly (≥10×) and report the result.
- **CI workflow currency** — whether the phase added a package, service, or
  deployable that must be registered in a CI matrix. Concretely:
  - `.github/workflows/build-and-scan.yml`'s Docker matrix currently lists **14
    `services/*` entries only**. `agent-os/*` components have **no Dockerfile**
    and appear in neither this matrix nor `infra/docker/docker-compose.local.yml`.
    A phase that makes an `agent-os` component deployable must close that gap or
    explicitly record it as deferred. (Phase 3E took the second route: recorded
    as a ratified deferred obligation in
    [`08-tdd-3e-agent-os.md`](design/phase-3/08-tdd-3e-agent-os.md) §15, with a
    criterion-by-criterion demonstration that no Phase 3E acceptance criterion
    requires a deployed container.)
  - **`agents/*` are not workspace members and are not covered by
    `pnpm turbo run lint`/`test`.** They are Agent Packages (doc 02 `:162-169`),
    with no `package.json` and no `pyproject.toml`, and each exposes a module
    named `handler`, so one pytest or mypy process cannot collect them together.
    `pr-checks.yml` therefore runs them as a **per-package loop** plus a single
    `ruff check agents/`. A phase adding an Agent Package inherits that loop
    automatically; a phase changing the layout must keep it working.
  - `.github/workflows/real-infra-checks.yml`'s matrix currently lists **11**
    packages; a new package with `real_infra` tests must be added. (Was 10
    until Phase 3E added `reasoning-engine` — the count is corrected here
    rather than left stale, per §6.3's living-reference rule.)
  - `pyproject.toml` `[tool.uv.workspace]` members and `pnpm-workspace.yaml`
    packages must include any new workspace member.

### 9.3 What must be updated

- CI matrices, workspace globs, and `[tool.importlinter]` `root_packages` for any
  new package/engine/component.
- `docs/architecture/17-cicd-pipeline.md` and `16-testing-strategy.md` if the
  gates themselves changed.

### 9.4 What must be reported

A results table with real numbers:

| Gate | Command | Result |
|---|---|---|
| Lint + types | `pnpm turbo run lint` | e.g. 26/26 pass; N source files per package |
| Tests (uncached) | `pnpm turbo run test --force` | 26/26 pass; per-package passed/deselected counts |
| Coverage | per-package `--cov` | actual % per affected package vs the 85% gate |
| Import boundaries | `uv run lint-imports` | "N kept, 0 broken" |
| Scaffolding tools | `uv run pytest tools/tests -q` | count |
| compose | `docker compose … config` | valid / errors |
| Codegen drift | generate + `git status` | file count; drift or none |

Plus: the negative-control result for every property-asserting test; the
flakiness result for every timing-sensitive test; and every gate **not** run,
with the reason.

---

## 10. Real-infrastructure test verification

### 10.1 What must be checked

- Whether the phase touched persistence, messaging, or any real backing store.
  If it did, `real_infra` tests are **expected** — their absence is a finding.
- Whether a Docker daemon is actually available:
  ```bash
  docker info >/dev/null 2>&1 && echo available || echo NOT available
  ```
  This project's remote sessions frequently have **no Docker daemon**. That is a
  disclosure obligation, not a pass.
- **Exactly which tests were deselected**, enumerated by name — not merely
  counted:
  ```bash
  uv run --package <pkg> pytest -m real_infra --collect-only -q
  ```
- For each deselected test: **does it cover code this phase changed?** A phase
  that changed only domain logic and no repository code has a materially
  different exposure from one that changed a repository. State which, with the
  diff as evidence.
- Whether `.github/workflows/real-infra-checks.yml` covers the affected package
  (its matrix currently lists nova-testkit, communication-engine,
  personality-engine, perception-engine, digital-twin-engine, capability-engine,
  action-engine, planning-engine, **reasoning-engine**, kernel, registry —
  eleven; `reasoning-engine` was added by Phase 3E after a real-Postgres
  foreign-key defect survived from Phase 2B precisely because that engine had
  no entry here).
- That this workflow is **non-blocking and staged by design** — it is
  deliberately not a required status check. A green `pr-checks` run is therefore
  **not** evidence that real-infrastructure tests passed.

### 10.2 What must be reported — always as its own section

Real-infrastructure status is reported **separately** from the main test results,
never folded into an aggregate "all tests pass". The section must state:

1. Whether Docker was available, and the command output proving it.
2. Every deselected `real_infra` test, by full name.
3. For each: whether it exercises code this phase changed, with the reasoning.
4. Whether the package is in the `real-infra-checks.yml` matrix.
5. Whether the workflow has run against this phase's head SHA, and its
   conclusion.
6. An explicit sentence naming what remains unverified — e.g. *"These N tests
   have not been executed in any environment for this change; they remain covered
   only by the non-blocking CI workflow, which has not yet reported against SHA
   `<sha>`."*

**Never** report a real-infrastructure gap as closed on the strength of local
non-`real_infra` tests, and never omit the section because nothing ran.

---

## 11. PR, branch, commit, and CI evidence

### 11.1 What must be checked

```bash
git status --short                      # working tree must be clean
git branch --show-current               # the designated branch, not another
git log --oneline -<n>                  # the phase's commits
git show --stat HEAD                    # the diff actually committed
git log origin/<branch>..HEAD           # unpushed commits (must be empty)
git merge-base --is-ancestor <base> HEAD && echo "ancestry OK"
```

- **Working tree clean.** Uncommitted changes mean the verified state and the
  pushed state differ; nothing may be reported as complete until it is committed.
- **Correct branch.** Work is on the branch the user designated. Never push to a
  different branch without explicit permission.
- **Diff contains only intended changes.** Documentation-only changes contain no
  application code; implementation changes contain no undisclosed scope creep.
  Read `git show --stat` and confirm the file list matches what was described.
- **Commit messages are accurate.** Every factual claim in a commit message —
  test counts, file counts, what was verified — must be true. A wrong count in a
  commit message is a defect in the permanent record and must be corrected before
  the phase closes.
- **Head SHA recorded**, because every CI claim must be tied to it.
- **Real GitHub Actions CI**, not local verification, checked against that exact
  SHA: `pr-checks`, `build-and-scan` (including Trivy —
  `aquasecurity/trivy-action@v0.34.0`, `severity: CRITICAL,HIGH`, `exit-code: 1`),
  and `real-infra-checks` (non-blocking). Record each workflow's conclusion and
  its run URL or ID.
- **PR state**, if a PR exists: number, base branch, mergeability, review state,
  and whether a merge conflict or stale base needs resolving.
- **Whether a PR should exist at all.** No PR is opened unless the user has
  explicitly asked for one. A standing "no PR yet" instruction persists across
  slices until the user lifts it.
- **Branch hygiene**: stale branches, unmerged work, branches whose PR already
  merged (a merged PR is finished and must never be reused for follow-up work).

### 11.2 What must be reported

- Branch name, head SHA, clean-tree confirmation.
- The commit list for this phase, with each message's factual claims verified.
- The `git show --stat` file list, confirmed to match the described scope.
- Per CI workflow: name, conclusion, the SHA it ran against, and its run
  reference. Where CI has not run or is unreachable from the session, say so
  plainly — **a local pass is never reported as CI evidence.**
- PR number and state, or an explicit statement that no PR exists and why.
- Trivy result if any Dockerfile was touched.

---

## 12. Cross-file consistency verification

### 12.1 What must be checked

The question is narrow and absolute: **does any document in the repository
contradict the repository's current state, or contradict another document?**

Consistency axes, each checked explicitly:

1. **Counts.** Engines, packages, `agent-os` components, agent packages, ADRs,
   import-linter contracts, CI matrix entries, generated TypeScript files. Every
   count asserted anywhere in `docs/` or any README is reconciled against a
   command that produces the real number.
2. **Names.** Every class, module, event subject, RPC subject, table, endpoint,
   and file path named in documentation resolves in the repository. Renames leave
   stale references behind; grep for the old name across all of `docs/` and every
   README.
3. **Status claims.** Phase status appears in `README.md`,
   `ENGINEERING_ROADMAP.md`, `project-health-master.md`, individual
   `phase-N.md` records, Gate Reviews, and design documents. All must agree.
4. **Ownership claims.** Which engine owns which state must read identically in
   the relevant ADR, `20-engine-responsibility-boundaries.md`, the TDD, and the
   code.
5. **Deferral claims.** A document saying "deferred to Phase N" that Phase N has
   now delivered is a contradiction. So is a document claiming something ships
   that does not exist.
6. **Verification claims.** A Gate Review asserting real-infrastructure
   verification that never ran; a Project Health record citing a coverage figure
   no run produced. Every cited number must trace to a real result.
7. **Cross-document citations.** Where document A cites document B section §X,
   open B and confirm §X says what A claims. **This includes citations inside
   source code.**

### 12.2 What must be reported

- Each axis, with the command or inspection used and the result.
- A contradiction table: document A claim → document B claim (or repository
  fact) → which is correct → correction made.
- Explicit confirmation that **no unresolved contradiction remains**, or a list
  of those that do, escalated to category 13.

---

## 13. Gaps, ambiguities, and decisions requiring the user's approval

### 13.1 What must be collected

Every one of the following, from every prior category:

- **Architectural ambiguities** — where the TDDs, ADRs, Bible, and architecture
  documents do not determine the answer, and implementing either way is a real
  architectural decision. **Stop and report; do not decide unilaterally.**
- **Contradictions between authoritative documents** that this protocol could not
  resolve without a judgment call.
- **Missing mechanisms** — a required capability the architecture has no defined
  home for.
- **Narrowings and reinterpretations** — anywhere the implementation is narrower
  or broader than a document's literal text. Each needs explicit approval, and
  the narrowing must be recorded in both the code and the design documentation.
- **Unverified items** — anything category 9, 10, or 11 could not execute.
- **Scope questions** — work discovered that belongs to this phase but was not
  planned, or planned work that turned out to belong elsewhere.
- **Deferred-obligations ledger rows** (§0.2) still unsettled.
- **Newly discovered defects** outside the phase's scope — reported, not silently
  fixed and not silently ignored.

### 13.2 How each must be reported

For each item:

1. **What the ambiguity or gap is**, in one or two sentences.
2. **The documents consulted**, with sections, and precisely what each does and
   does not say. Where a document is silent, say *"§X is silent on this"* rather
   than inferring intent from silence.
3. **The options**, with the concrete consequences of each.
4. **A recommendation**, with reasoning — a recommendation, not a decision taken.
5. **What is blocked** until the user decides, and what can proceed regardless.

### 13.3 The stop rule

> If the work reveals an architectural ambiguity or a missing mechanism, **stop
> and report it before making the architectural decision.** Deliver everything
> that does not depend on the answer; state the question at the point it arises.

A decision the user has already made is not reopened by this rule. A decision
nobody has made is never made silently.

---

## 14. Documentation updates required by implementation changes

### 14.1 The trigger table

This category is mechanical: given what the implementation changed, these
documents **must** be inspected and updated where affected. Work the table in
both directions — from change to documents, and from documents back to the
change.

| If the phase changed… | Then inspect and update… |
|---|---|
| A new engine / package / `agent-os` component | `02-repository-and-folder-structure.md`; `pyproject.toml` (`[tool.uv.workspace]`, `[tool.importlinter]` `root_packages` + contract `modules`); `pnpm-workspace.yaml`; CI matrices in `build-and-scan.yml` and `real-infra-checks.yml`; `infra/docker/docker-compose.local.yml`; the subsystem's own `README.md`; the top-level `README.md` engine count |
| A new or changed event / RPC subject | `packages/nova-contracts/`; its contract test; `09-event-bus-architecture.md`; `10-inter-engine-communication.md`; publisher and subscriber READMEs; regenerated TypeScript |
| A REST endpoint | `11-api-architecture.md`; the engine's `README.md`; OpenAPI backward-compatibility review (SAD 15 §4 item 4) |
| A database table / migration | `07-database-architecture.md`; the engine's Alembic `versions/`; `real_infra` repository tests |
| State ownership or an engine boundary | The governing ADR (new ADR if the decision changed); `20-engine-responsibility-boundaries.md`; both engines' TDDs; both READMEs |
| Agent / NAOS behavior | `12-agent-architecture.md` (incl. §15's ships-in-Phase-3 table); `docs/design/phase-3/08-tdd-3e-agent-os.md`; the affected `agents/*/README.md` and `agent-os/*/README.md` |
| A test tier, marker, or coverage rule | `16-testing-strategy.md`; ADR-033; `pyproject.toml` `[tool.pytest.ini_options]` / `[tool.coverage.report]` |
| A CI workflow or gate | `17-cicd-pipeline.md`; `15-development-workflow.md` §4 |
| An observability metric or log | The engine's `observability.py`; `01-technology-stack.md`; SAD 15 §9.1 items 9–10 |
| A Dockerfile or deployment surface | `14-deployment-architecture.md`; `infra/docker/README.md`; `build-and-scan.yml` matrix; Trivy results |
| An approved narrowing of a design document | The design document (additively); the module docstring carrying the decision; the Gate Review |
| A shared package (`nova-service-kit`, `nova-testkit`, `nova-eventbus-sdk`, …) | `docs/design/<package>/`; the package `README.md`; ADR-033 / ADR-034 boundary contracts; **every consumer** |

### 14.2 SAD 15 §9.1 — the ten-item build-time deliverable checklist

For **every subsystem the phase introduced**, confirm all ten items of
[SAD 15 §9.1](architecture/15-development-workflow.md#91-the-ten-item-build-time-deliverable-checklist)
exist: architecture documentation, sequence diagrams, component diagrams, API
documentation, unit tests, integration tests, performance benchmarks, failure
scenarios, logging strategy, observability metrics. Report each as present or
absent. **Documentation, tests, and observability are part of the
implementation, not an afterthought** — a missing item is an incomplete
subsystem, not a documentation debt.

### 14.3 What must be reported

- The trigger table, filled in for this phase: what changed → what was inspected
  → what was updated → what needed no change.
- The SAD 15 §9.1 ten-item status for every new subsystem.
- Every document updated, with its before/after text.
- Every document inspected and found accurate — the evidence the sweep was real.

---

## 15. The mandatory final checklist

Before declaring a Phase, Sub-Phase, or Slice complete, every line below must be
answered **Yes** or **N/A with a stated reason**. A **No** blocks completion.

**Implementation and design**
1. Every TDD requirement checked against source, with a conformance table? □
2. Every relevant ADR checked in both directions? □
3. Every user-approved decision verified as implemented? □
4. Every deviation classified and either approved or reported? □
5. Every citation in documentation *and in source docstrings* verified? □

**Acceptance criteria**
6. Every criterion enumerated from all sources (TDD, research docs, roadmap,
   in-session) and given an evidence-backed status? □
7. The "N of M met" sentence written, with unmet criteria named? □

**Verification**
8. `pnpm turbo run lint` — pass, with counts? □
9. `pnpm turbo run test --force` (**uncached**) — pass, with counts? □
10. 85% domain coverage met for every affected package, actual % recorded? □
11. `uv run lint-imports` — 0 broken? □
12. `uv run pytest tools/tests -q` — pass? □
13. `docker compose … config` — valid? □
14. Codegen regenerated, drift confirmed zero? □
15. Every property-asserting test negative-controlled (fails when the property is
    removed)? □
16. Timing-sensitive tests run repeatedly for flakiness? □

**Real infrastructure**
17. Docker availability determined and stated? □
18. Every deselected `real_infra` test enumerated by name? □
19. Each assessed for whether it covers code this phase changed? □
20. The unverified set stated explicitly, in its own section? □

**Evidence**
21. Working tree clean; correct branch; head SHA recorded? □
22. `git show --stat` confirms the diff contains only intended changes? □
23. Every factual claim in every commit message verified true? □
24. Real CI conclusions recorded against that exact SHA (or their absence stated)? □
25. PR state recorded — or the explicit statement that no PR exists, and why? □

**Documentation**
26. `docs/` staleness sweep run, with the grep commands and hit counts reported? □
27. Every affected architecture document inspected? □
28. Every affected ADR inspected? □
29. Bible compatibility re-checked (Bible not edited without approval)? □
30. Every affected README inspected, with a verdict each? □
31. Top-level `README.md` Status section verified against the repository? □
32. The category-14 trigger table filled in? □
33. SAD 15 §9.1's ten items confirmed for every new subsystem? □

**Records**
34. `ENGINEERING_ROADMAP.md`'s phase entry reflects actual status? □
35. Gate Review written, following the established structure? □
36. Project Metrics section present, per SAD 15 §10 / `METRICS_TEMPLATE.md`? □
37. SLOC milestones (~30k reminder, ~50k gate) checked and surfaced if crossed? □
38. `docs/project-health/phase-<N>.md` written in the 23-field shape, every value
    cited? □
39. `project-health-master.md` table row added; §2 updated if methodology changed? □
40. All ten `definition-of-done.md` items confirmed? □

**Consistency and closure**
41. All seven consistency axes checked; no unresolved contradiction? □
42. Every deferred-obligations ledger row from every Slice settled? □
43. Every gap, ambiguity, and decision-for-approval collected into category 13
    with options and a recommendation? □
44. The gate verdict stated as **GO**, **CONDITIONAL-GO**, or **NO-GO**, with
    conditions or blockers enumerated? □
45. Every category of this protocol addressed in the report, including those
    marked N/A with a reason? □
46. The report contains **no claim that was not verified in this session**? □
47. Explicit confirmation that completing this phase is **not** authorization to
    begin the next? □

---

## 16. What the final report must contain

Every Phase, Sub-Phase, or Slice completion report is structured by this
protocol's categories, in this order, with none omitted:

1. Scope executed, and what was deliberately not executed
2. Implementation vs TDD / ADR / approved decisions — conformance + deviations
3. Acceptance criteria table, with the "N of M" sentence
4. Contract and codegen verification
5. Test, lint, type, coverage, import-linter results — real numbers, uncached
6. Negative-control and flakiness results
7. **Real-infrastructure status — its own section, never merged into (5)**
8. Branch, commit, diff, and CI evidence, tied to an exact SHA
9. Documentation updates made — with before/after text
10. Documents inspected and found accurate
11. Cross-file consistency results
12. Gaps, ambiguities, and decisions requiring approval — with recommendations
13. Deferred-obligations ledger (Slices) or its settlement (Phases)
14. Gate verdict: GO / CONDITIONAL-GO / NO-GO
15. Explicit statement of what was **not** verified, and why

---

## 17. Relationship to existing policies

This protocol **subsumes and operationalizes** — it does not replace — three
existing standing policies. Where any of them is more specific, the more specific
text governs; where this protocol is stricter, this protocol governs.

- [`docs/project-health/definition-of-done.md`](project-health/definition-of-done.md)
  — the ten-item phase-level completion checklist. Every item is required here
  (checklist lines 34–40); this protocol adds the verification method, the
  inspection surface, and the reporting obligations around them.
- [`docs/architecture/15-development-workflow.md` §4](architecture/15-development-workflow.md#4-definition-of-done-per-pr)
  (per-PR Definition of Done), [§8](architecture/15-development-workflow.md#8-the-permanent-subsystem-lifecycle)
  (the permanent subsystem lifecycle), [§9](architecture/15-development-workflow.md#9-per-subsystem-deliverable-checklist)
  (required TDD contents + the ten-item build-time deliverable checklist), and
  [§10](architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate)
  (Project Metrics and the SLOC milestone gates) — all still apply in full.
- [`docs/project-health/README.md`](project-health/README.md) — the rule that a
  phase is not closed until both its Gate Review and its Project Health record
  exist, and the 23-field record shape.

**Reading order when closing a phase:** this protocol first (it tells you what to
execute and in what order), then `definition-of-done.md`, then SAD 15 §4/§8/§9/§10
for the per-PR and per-subsystem detail, then `project-health/README.md` for the
record shape.

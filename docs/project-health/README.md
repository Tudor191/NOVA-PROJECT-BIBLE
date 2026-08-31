# Project Health

This directory is the permanent, longitudinal record of NOVA's project health across every Phase and Sub-Phase — a companion to, and explicitly distinct from, this project's Gate Reviews.

## What Project Health is

A structured, chronological snapshot of the same handful of facts — code size, test health, coverage, CI status, real-infrastructure verification, documentation health, architecture status, open blockers — captured once per completed Phase/Sub-Phase, in one consistent shape, so the project's health can be read across time without re-reading a dozen individual Gate Reviews and reconstructing the trend by hand.

## Why this directory exists

`docs/roadmap/architecture-reviews/` already accumulates one Gate Review per Phase/Sub-Phase, and those documents are detailed, excellent, and authoritative for *that phase's own* review. But a 2026-08 audit of this repository found that the standing, permanent Project Metrics requirement established at the Phase 1 Gate Review ([SAD 15 §10](../architecture/15-development-workflow.md#10-project-metrics--the-sloc-milestone-gate)) — full compliance through six consecutive phases — had quietly degraded and then stopped appearing in reports entirely for the last several phases, with no single document anywhere making that drift visible as it happened. This directory exists specifically so that never has to be rediscovered by audit again: one place, one shape, updated every time a phase closes, whether or not that phase's own Gate Review remembers to include the section SAD 15 §10 requires.

## Gate Review vs. Project Health

**Gate Review = detailed, phase-specific review.** Written once, for that phase, covering everything specific to what that phase built: architecture decisions, forks resolved, files changed, the full verification tier breakdown, known limitations. It stays exactly as it was written — a historical record of that phase's own review, never retroactively edited to fit a different phase's format.

**Project Health = permanent, longitudinal project-health history.** A much narrower, standardized slice of the same information — the same 23 fields, every time — organized for reading *across* phases, not *within* one. It is built *from* Gate Reviews (and, where a Gate Review omits a field, explicitly says so), never the other way around; Project Health never overrides or corrects a Gate Review's own content.

**The rule going forward: every completed Phase/Sub-Phase must update `docs/project-health/`, not just file its own Gate Review.** A phase is not fully closed until both exist — see [`definition-of-done.md`](definition-of-done.md) for the complete, ten-item phase-level completion checklist this rule is one part of.

## How historical records are represented

Each Phase/Sub-Phase gets its own file (`phase-N.md`), containing a standardized 23-field snapshot (phase identity, date, branch, PR, commit, status, SLOC ×4 fields, tests ×2 fields, coverage, CI, real-infrastructure, documentation health, architecture status, security status, unverified infrastructure, open blockers, branch hygiene, notes). Every value is cited back to its source document — usually a specific line number in that phase's own Gate Review — so any figure here can be independently re-verified against the original at any time. `project-health-master.md` is the chronological index: one summary table across every phase, plus links out to each individual record.

Where a phase shipped as multiple separately-reviewed PR-sized units (Phase 3B is the current example — Domain Foundation and Decomposition Orchestration each got their own Gate Review), the corresponding Project Health file keeps them as clearly separated sub-sections rather than merging their numbers into one misleading combined figure.

## How SLOC methodology is recorded

Every SLOC figure carries its **tool** (`cloc` or `scc`, and the exact flags used, e.g. `--skip-uniqueness`) and its **scope** (which directories were counted — this has itself changed at least once in this project's history) alongside the number itself, never the number alone. `project-health-master.md` §2 is the dedicated methodology-history section: it documents every tool/scope change found in the source Gate Reviews, in order, including places where one phase's own document claimed continuity with a prior one that a closer reading shows didn't actually hold. When two SLOC figures used different tools or different scope, they are **not** silently treated as one continuous series.

## How missing historical data is represented

If a source document does not state a value, the field reads **"Not reported."** This system never calculates, estimates, infers, or backfills a historical value from today's repository state, and never averages a missing figure in from an adjacent phase. A "Not reported" field is itself informative — it tells you the gap existed at the time, not just that this system doesn't happen to have the number.

## How incomparable measurements are represented

When two measurements exist but used different tools, different scope, or otherwise can't be read as one trend, they are recorded side by side with an explicit label — e.g. *"Current informational measurement, `cloc`, not comparable to the historical `scc` series"* — rather than merged, averaged, or silently presented as continuous. See `project-health-master.md` §2 for the concrete example this project already has.

## How future phases must update this system

When a Phase/Sub-Phase's Gate Review is written, its author also writes (or extends, for a multi-PR phase like 3B) that phase's own `docs/project-health/phase-N.md` file using the same 23-field shape, cites every value back to the Gate Review section it came from, and updates `project-health-master.md`'s summary table and, if the SLOC methodology changed again, its §2 history section. If a metric is unavailable for that phase, write "Not reported" or "Not measured" in that field — never omit the field silently, and never leave the table row blank without an explanation of why.

## Definition of Done

[`definition-of-done.md`](definition-of-done.md) is the permanent, standing
phase-level completion checklist — Gate Review and Project Health record (this
directory) are two of its ten items, alongside TDD/design-doc currency, roadmap and
README status, reconciliation notes for historical corrections, tests/CI/Trivy/
real-infrastructure evidence, final acceptance-criteria status, and a final
merge-readiness review. Read it before declaring any future Phase or Sub-Phase
complete.

## Source of truth

**`project-health-master.md` is the longitudinal source of truth for project health across NOVA's history.** Individual `phase-N.md` files are its supporting detail, each independently citable back to its own Gate Review. Gate Reviews remain the authoritative, detailed record for what happened *within* a given phase; Project Health is the authoritative record for the trend *across* phases.

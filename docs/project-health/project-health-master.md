# NOVA Project Health — Master Index

The longitudinal, chronological record of every Phase/Sub-Phase's project-health data, built exclusively from what each phase's own Gate Review, Architecture Review, or the one-time Project Health Review actually reported. **No value in this document is calculated, estimated, or backfilled from the current repository state unless explicitly labeled as such.** Where a source document does not report a field, this document says **"Not reported"** — it does not guess, and it does not average a value in from adjacent phases.

See `README.md` in this directory for what this system is, how it differs from a Gate Review, and how to update it going forward.

---

## 1. Master timeline

| Phase | Status | Production SLOC | Total SLOC | SLOC Methodology | Tests | Coverage | CI | Real Infra | Documentation |
|---|---|---|---|---|---|---|---|---|---|
| [Phase 1](phase-1.md) | Go | 9,794 | 30,946 | `cloc --skip-uniqueness` | 376 | 79% | Pass (local) | Not exercised (no Docker) | Healthy, 1 stale artifact fixed in-review |
| [Phase 2A](phase-2a.md) | Go | 12,412 | 38,541 | `cloc` (no `--skip-uniqueness` — later flagged as not comparable) | 480 | NR (aggregate); 84% new engine only | Pass (local) | Not exercised | Healthy, 1 stale artifact fixed in-review |
| [Phase 2B](phase-2b.md) | Go | 15,326 | 45,544 | `cloc --skip-uniqueness` (corrected back) | 558 | 80.3% | Pass (local) | Partial — first-ever native-Postgres round trip, ad hoc | Healthy |
| [Phase 2C](phase-2c.md) | Go | 17,116 | 51,763 | `cloc --skip-uniqueness` | 637 | 80.7% | Pass (local) | Partial — deeper native-Postgres round trip, ad hoc | Healthy, 1 self-reported arithmetic discrepancy (101 vs 102) |
| [Phase 2D-A](phase-2d-a.md) | Go (1 item flagged for explicit user decision) | 20,969 | 61,387 | `cloc --skip-uniqueness` | 804 | 79.0% | Pass (local) | Not exercised | Healthy |
| [Phase 2D-B](phase-2d-b.md) | Go | 31,610 | 77,286 | **`scc`** (tool changed from `cloc`) | 951 | 78.7% | Pass (local) | Not exercised, 3-engine backlog | Healthy — crossed the 30,000 SLOC Project Health Review threshold |
| [Project Health Review (2026-08)](../roadmap/architecture-reviews/project-health-review-2026-08.md) | Proceed to 2D-C, after a small cleanup pass | 31,610 (re-confirmed unchanged) | 77,939 | `scc` | N/A (review only) | N/A | N/A | N/A | Deep one-time review — 1 High, several Medium/Low findings (see §2) |
| [Phase 2D-C](phase-2d-c.md) | Gate passed, Option B, explicitly disclosed as incomplete | 33,175 | 85,141 | `scc` (claimed "consistent with every prior gate review") | 1,008 | 99.37% (communication-engine negative control) | Pass (local only, no GH Actions run cited) | Written, not executable (no Docker) | Healthy, scope explicitly bounded by the user's own instruction |
| [Phase 2D-C Closure — Priority 5](phase-2d-c-closure.md) | Go | 24,959 (narrower scope — **not comparable**, see §2) | NR | **`cloc`** (tool changed again, silently, contradicting 2D-C's own consistency claim) | 18/18 packages pass | 99.22% / 100% (`style_selector.py`) | Pass (local only) | N/A (no schema/DB change) | 1 unrelated documentation drift noted, explicitly not fixed |
| [Phase 2D-D](phase-2d-d.md) | Complete | NR (no SLOC section) | NR | NR | 1,179 passed, 45 deselected | 98.70% / 98.85% (negative controls) | Pass (local) | **Fully real-infra confirmed**, 2 real GitHub Actions runs, 1 real bug found and fixed | Healthy |
| [Phase 3A](phase-3a.md) | Complete | NR (delta only: +160) | NR | NR | 87 | 94% | Pass (local; monorepo 19/19, 1185/1185) | N/A, correctly (no new persistence/subject) | Healthy |
| [Phase 3B — Domain Foundation (PR #2)](phase-3b.md) | Complete, 1 real bug + 1 coverage-claim error fixed by independent post-review pass | NR | NR | NR | 35 | 100% (corrected from an inaccurate original 100% claim) | `checks` pass; `build-and-scan` pre-existing unrelated failure | N/A (no persistence yet) | 1 disclosed deviation from TDD 3B's own proposal |
| [Phase 3B — Decomposition Orchestration (PR #7)](phase-3b.md) | Complete | NR | NR | NR | 57 | 99% branch | 3/3 workflows green, real GitHub Actions (18 check runs) | Partial — real NATS JetStream round trip explicitly unverified | **Documentation-sync gap identified**: its own cited research (`phase-3b-decomposition-research`, commit `654570d`) remains unmerged into the canonical lineage as of this record |
| [Phase 3B — Planning Persistence (`phase-3b-planning-persistence`, PR #18)](phase-3b.md) | Complete, fully verified locally and via real GitHub Actions; not yet merged | NR | NR | NR | 67 passed, 10 real-infra deselected (77 total) | 98.68% domain | 24/24 checks green, real GitHub Actions, head `ac364b9` | Fully real-infra confirmed via CI: 10/10 real-Postgres tests passed against a real `postgres:16-alpine` container (first-ever `planning-engine` real-infra matrix entry); one genuine defect (unstringified `depends_on` UUIDs) caught by the first push and fixed same-day | Closes TDD 3B §4/§5/§6.2 — TDD 3B status banner and both prior Phase 3B Gate Reviews additively updated; dated Phase 3E research reconciliation note added, no Phase 3E decision reopened |
| [Phase 3C](phase-3c.md) | Complete, merged (PR #8) | NR in the gate review itself | NR in the gate review itself | NR in the gate review itself | 59 passed, 6 deselected | 97% | 20/20 green, real GitHub Actions, re-confirmed live post-merge | Fully real-infra confirmed after a mid-review CI-matrix fix | Resolved — `phase-3c-research`'s decisions synced into canonical TDD 3C via PR #11 (2026-08-17) |
| [Phase 3D](phase-3d.md) | **Go** — all 7 of TDD 3D §14's acceptance criteria met (deep `Capability.input_schema` validation at stage 5, the last gap, closed 2026-08-18 by PR #13 commit `046d459`); CI 22/22 green; **merged into `phase-3b-planning-domain` 2026-08-18** as squash commit `ac285bc3533fb24d0434d7675b8fc3af2db1d079` — see the [Gate Review](../roadmap/architecture-reviews/phase-3d-action-engine-gate-review.md) | NR | NR | NR | 62 passed, 8 deselected (action-engine, up from 47 after the deep-validation commit); capability-engine/nova-contracts unaffected, re-verified 61 passed / 86 passed | 97% (action-engine domain, incl. 100% on the new `parameter_validation.py`); capability-engine domain unchanged at 97% | 22/22 green, real GitHub Actions, re-confirmed live at head `046d459` (2026-08-18) | Fully real-infra confirmed via CI (8/8 real-Postgres tests, Docker build + Trivy scan) | Two additive TDD 3D §14 notes landed (2026-08-18): one disclosing the deep-validation gap, one recording its same-day closure; Gate Review updated twice the same day (Conditional → Go); `phase-3d-research`/PR #12 itself deliberately not synced into canonical lineage until both implementation PRs merged, per the same sequencing precedent PR #11 established (research syncs after its implementation PR merges, not before). **Update (2026-08-18):** PR #14 also merged the same day (merge commit `e9ea3b8c6ae99c645e6eb41b98fbe34c55f8ec39`), satisfying that precedent's condition. **Update (2026-08-19):** the sync itself is now complete — PR #15 (`phase-3d-research-sync`) merged as commit `bf748d0ef4157da3a60e0eb880a24a58264d9387`; all Phase 3D-relevant documentation (implementation, closure, and research) is now fully in canonical lineage |

`NR` = Not reported in the source document. A blank methodology/scope cell is never inferred from a neighboring phase.

---

## 2. SLOC methodology history — read before comparing any two numbers in the table above

**Do not treat the Production SLOC column above as one continuous series.** Assembling this master index surfaced a longer, more tangled tooling history than "scc replaced cloc" — it is preserved here in full because several of the individual gate reviews' own claims of methodology continuity do not hold up against each other:

1. **Phase 1** — `cloc --skip-uniqueness`.
2. **Phase 2A** — `cloc`, **without** `--skip-uniqueness`. Phase 2B's own gate review later states plainly that this makes Phase 2A's figure not directly comparable: "having confirmed that plain `cloc` silently deduplicates identical scaffolded files (`alembic.ini`, `script.py.mako`) across engines — Phase 2A's own SLOC figures were not re-measured with this flag."
3. **Phase 2B** — `cloc --skip-uniqueness` (corrected back).
4. **Phase 2C** — `cloc --skip-uniqueness`.
5. **Phase 2D-A** — `cloc --skip-uniqueness`.
6. **Phase 2D-B** — switches to **`scc`**, disclosed explicitly, not silently. The source text itself contains an apparent internal error worth flagging rather than fixing: it calls `--skip-uniqueness` a "Phase 2D-A-era `scc` flag," when Phase 2D-A's own gate review states it used `cloc --skip-uniqueness`, not `scc` — `--skip-uniqueness` is a `cloc` flag. Preserved verbatim in `phase-2d-b.md`, not silently corrected here.
7. **Project Health Review (2026-08)** — `scc`, consistent with Phase 2D-B, re-confirms the same 31,610 figure.
8. **Phase 2D-C** — `scc`, and its own text explicitly claims this is "consistent with every prior gate review's methodology." True relative to 2D-B and the Project Health Review; **not true relative to Phases 1 through 2D-A**, which used `cloc`.
9. **Phase 2D-C Closure — Priority 5** — switches back to **`cloc`**, silently (no disclosure comparable to 2D-B's own), and additionally narrows the *scope* from `src/` + Alembic `versions/` to `services/*/src` + `packages/*/src` only (no migrations counted at all). This directly contradicts Phase 2D-C's own "consistent with every prior gate review" claim, one report later.
10. **Phase 2D-D, Phase 3A, all three Phase 3B units, Phase 3C, Phase 3D** — **no Production SLOC or Total SLOC figure reported at all.** This is the reporting gap this whole `docs/project-health/` system exists to make visible and prevent from recurring silently.
11. **This project-health audit itself** (informational only, not phase-attributed): a fresh `cloc` measurement taken directly against the post-Phase-3C merged tree — **Production SLOC: 28,742; Total SLOC: 96,262** (`services/*/src` + `packages/*/src` + Alembic `versions/`, `cloc`, excluding blanks/comments). **This number is explicitly not inserted into the historical series above as though it continues it.** It is lower than Phase 2D-C's `scc`-measured 33,175 despite substantial code having been added since — most plausibly because `cloc` and `scc` are known to disagree on how Python docstrings are counted (comment vs. code), not because code was removed. Label if cited elsewhere: **"Current informational measurement, `cloc`, not comparable to the historical `scc` series."**

**Open methodology decision, left explicitly open, not decided here:**

- **Option A** — restore `scc` as the measurement tool (matching Phase 2D-B through Phase 2D-C, the most recent tool actually used when a figure was still being reported) and install it in every environment that produces a Gate Review.
- **Option B** — formally establish `cloc` (with a fixed, documented scope and flag set) as the new baseline going forward, explicitly superseding the `scc` series rather than trying to reconcile with it.

**This decision requires the user's explicit approval and is not made by this document.**

---

## 3. Historical records index

Individual, per-phase snapshot files, each citing its own source document by exact line number wherever a value is drawn from one:

- [`phase-1.md`](phase-1.md)
- [`phase-2a.md`](phase-2a.md)
- [`phase-2b.md`](phase-2b.md)
- [`phase-2c.md`](phase-2c.md)
- [`phase-2d-a.md`](phase-2d-a.md)
- [`phase-2d-b.md`](phase-2d-b.md)
- [`phase-2d-c.md`](phase-2d-c.md)
- [`phase-2d-c-closure.md`](phase-2d-c-closure.md) (Priority 5 only — Priorities 1-4 and 6 have no dedicated Gate Review document of their own found during this research pass, and are therefore not separately recorded here)
- [`phase-2d-d.md`](phase-2d-d.md)
- [`phase-3a.md`](phase-3a.md)
- [`phase-3b.md`](phase-3b.md) (covers PR #2 — Domain Foundation, PR #7 — Decomposition Orchestration, and `phase-3b-planning-persistence` — Planning Persistence, as three clearly separated sub-units, per their own separate Gate Reviews)
- [`phase-3c.md`](phase-3c.md)
- [`phase-3d.md`](phase-3d.md)

The one-time [Project Health Review (August 2026)](../roadmap/architecture-reviews/project-health-review-2026-08.md) is referenced throughout this index but intentionally kept in its existing canonical location under `docs/roadmap/architecture-reviews/` rather than duplicated here — it is a comprehensive, cross-phase architecture audit, not a per-phase snapshot, and per SAD 15 §10 it is triggered by the 30,000/50,000 SLOC milestones rather than by phase boundaries.

---

## 4. Current Project Health Monitoring classification

**`ACTIVE BUT NOT REPORTED`** — carried forward unchanged from the audit that established this classification. The Project Metrics / Production SLOC requirement under SAD 15 §10 remains standing, permanent policy (never rescinded), and the tooling to compute it still works. It has not been included in the last several phase reports (§1 above shows the exact pattern: full compliance through Phase 2D-B, degraded to a bare delta for 2D-C/3A, absent entirely from 2D-D, all three Phase 3B units, Phase 3C, and Phase 3D). This document does not claim monitoring was removed, and does not claim the historical `scc`-era and `cloc`-era measurements are currently comparable.

See `README.md` for how this classification is meant to be kept current going forward.

# Phase 2B — Project Health Snapshot

Source: `docs/roadmap/architecture-reviews/phase-2b-gate-review.md` (read in full for this snapshot; every value below is cited to a specific line).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 2B |
| 2 | Phase/Sub-Phase name | Reasoning Engine (Bible Part 8) |
| 3 | Report date | **2026-08-05** (`:4`) |
| 4 | Branch | Not reported |
| 5 | PR number | No PR — direct commit workflow (git-history-derived; commit `ace05a3` carries no PR reference) |
| 6 | Commit / merge commit | Not reported |
| 7 | Phase status | "**Go.**" (`:572`). Closing: "Phase 2B is closed." (`:593`) |
| 8 | Production SLOC | **15,326** — application `src/` (15,044, measured with `--skip-uniqueness`) + Alembic migrations (282, 5 files) (`:625-629, 639`). Prior phase (2A) baseline in the same table: 12,412. |
| 9 | Total SLOC | **45,544** (all tracked languages, all purposes), up from 38,541 (`:633`) |
| 10 | SLOC methodology/tool | `cloc --skip-uniqueness`, `radon cc` + direct `ast` script, `grimp`, `git ls-files`/`du`, `pytest --cov` (`:602-604`). Explicit methodology correction disclosed in this document: "having confirmed that plain `cloc` silently deduplicates identical scaffolded files (`alembic.ini`, `script.py.mako`) across engines — Phase 2A's own SLOC figures were not re-measured with this flag." (`:605-611`) — i.e. Phase 2A's Production SLOC figure is **not directly comparable** to Phase 1's or this phase's own, by this document's own admission. |
| 11 | SLOC scope | Application `src/` (measured with `--skip-uniqueness`) + Alembic migrations (`:625-629`) |
| 12 | Test status | "**558 tests pass** across all 13 first-party packages (up from Phase 2A's 480), zero failures. The new engine alone contributes 69 (43 unit, 11 integration, 15 ADR-023 port-compliance)." (`:25-28`) |
| 13 | Test count | 558 (`:707`) |
| 14 | Coverage | Per-service: memory-engine 80%, knowledge-engine 79%, world-model-engine 73%, ai-model-orchestration-engine 84%, reasoning-engine 84% (1,352/223). Aggregate: **80.3%** (6,490 statements, 1,280 missed, combined) (`:712-713`) |
| 15 | CI status | Ruff: PASS, 0 issues. MyPy: PASS, 264 files. Import-linter: PASS, 4/4 contracts, 251 files / 1,135 deps (`:714-716`) |
| 16 | Real-infrastructure status | First real-Postgres verification in this project's history: "this sandbox has a native Postgres 16 instance available, used to boot the real `PostgresReasoningRepository` against a live database and run a genuine reason → persist → retrieve round trip ... every prior phase's Gate Review could only verify the Postgres-specific repository code via fakes ... That gap is now partially closed for this engine (ad hoc, not yet a committed CI-enforced test)." (`:45-51`) Still no Docker daemon (`:131-142`). |
| 17 | Documentation health | Generated TypeScript client: "804 (47 files including `index.ts`; regenerated and confirmed zero-diff this session — not stale)" (`:640`). Architecture documents: "94 total" (`:685`). |
| 18 | Architecture status | §15/§16 — same clean-compliance pattern. Liskov substitution "holds by construction: the ADR-023 port-compliance suite runs the identical test functions against each port's fake and its real-client (mock-transport-backed) implementation — 15 tests." (`:430-492`) |
| 19 | Security status | No hardcoded secrets, no raw SQL interpolation (8 `session.execute` sites checked directly), `pip-audit` zero known vulnerabilities, no auth (deferred to Phase 7), no CORS/rate limiting, non-root Dockerfile, Pydantic validation plus one genuine cross-field validation (`POST .../override`'s 400 for missing `redirect_alternative_id`) (`:181-203`) |
| 20 | Unverified infrastructure | No Docker daemon (partial improvement via native Postgres, still no full compose stack); no automated event-contract-drift check; no CORS/rate limiting; no admin API; no pagination convention; "No committed pytest coverage against a real Postgres instance, for any engine." Risks: Multi-step mode is single-pass not recursive; Constraint Evaluation's hard gate "has nothing real to check yet"; only one background worker instead of two-or-three (`:124-159`) |
| 21 | Open blockers | None block Phase 2C's design work, except item 2's latency verification (`:563-568`) |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | One issue found and fixed during this review: a dead, unused `outbox_poll_interval_seconds` config field, removed (`:103-116`). Two real correctness bugs found and fixed during the phase's own implementation (not this review): the `context_assembly.py` all-or-nothing degradation bug, and a missing `OutboxEventORM.id` Python-side default affecting both this engine and the already-shipped AI Model Orchestration Engine (`:55-60, 117-122`). "Zero new ADRs filed this phase ... the first phase in this project's history to file zero new ADRs." (`:736`) Highest-complexity function in the project's history to date: `pipeline.run` at "D, 27." (`:755`) 50,000 SLOC milestone: "15,326 / 50,000 ≈ 30.7%" (`:738`). |

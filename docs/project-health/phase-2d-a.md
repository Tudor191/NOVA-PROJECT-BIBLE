# Phase 2D-A — Project Health Snapshot

Source: `docs/roadmap/architecture-reviews/phase-2d-a-gate-review.md` (extracted via full-text research pass; every value below is cited to a specific line in that document).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 2D-A |
| 2 | Phase/Sub-Phase name | Voice & Communication Foundation (Bible Parts 13, 17) |
| 3 | Report date | **2026-08-07** (`phase-2d-a-gate-review.md:4`, stated explicitly as "**Date:**") |
| 4 | Branch | Not reported |
| 5 | PR number | Not reported (document neither states a PR number nor states no PR was used) |
| 6 | Commit / merge commit | Not reported |
| 7 | Phase status | "**Go**, with one finding flagged for explicit user attention rather than silently absorbed into a routine pass." ... "Phase 2D-A is closed, pending the user's explicit decision on Recommendation 10." (`:591, 624`) |
| 8 | Production SLOC | **20,969** — application `src/` (20,523) + Alembic migrations (446, 8 files) (`:649-653`). Prior phase (2C) baseline in the same table: 17,116 (`:663`). |
| 9 | Total SLOC | **61,387** (all tracked languages, all purposes), up from 51,763 (`:657`) |
| 10 | SLOC methodology/tool | `cloc --skip-uniqueness` (`:634-637`) |
| 11 | SLOC scope | Application `src/` + Alembic migrations; tests, dev tooling, generated TypeScript, and docs reported separately, never folded in (`:649-653`) |
| 12 | Test status | "**804 tests pass** across all 16 first-party packages (up from Phase 2C's 637), zero failures." (`:24`) |
| 13 | Test count | 804 (up from 637) (`:24, 709`) |
| 14 | Coverage | Aggregate over 8 production services: **79.0%** (9,228 stmts, 1,942 missed) — down ~1.7 points from Phase 2C's 80.7% (`:715`) |
| 15 | CI status | Ruff: PASS, 0 issues (whole repo). MyPy: PASS, 371 files across 16 packages, per-package invocation matching CI. import-linter: PASS, 4/4 contracts, 355 files / 1,580 deps (`:716-718`) |
| 16 | Real-infrastructure status | "No real-Postgres verification was performed for either new engine this phase" (personality-engine, communication-engine) — repository layers verified only via in-memory fakes; "No Docker daemon in this development environment, confirmed directly again this session." (`:61-65, 134-138`) |
| 17 | Documentation health | Documentation growth: 22,763 → **25,891** lines (+3,128). Architecture documents: **114 total** (98 in `docs/` + 16 READMEs) (`:730, 697`) |
| 18 | Architecture status | "The architecture is sound by every check available in this environment ... The foundation is ready to support Phase 2D-B, with the verification-depth regression noted above as this review's most significant finding — not a defect, but a real gap worth naming rather than silently carrying forward unremarked." (`:67-73`) |
| 19 | Security status | No hardcoded secrets found; no raw-SQL injection risk (one f-string-SQL exception found and evaluated as safe — hardcoded constants only); `pip-audit`/`pnpm audit` zero known vulnerabilities; no auth on any endpoint yet (deferred to Phase 7 per SAD 13, by design); both Dockerfiles run non-root; raw audio never persisted; Pydantic validates every request/event payload (`:184-207`) |
| 20 | Unverified infrastructure | No Docker daemon in this environment (blocks build/boot/network verification for every engine); no real-Postgres verification for either new engine; no automated event-contract-drift check (manual); no CORS/rate limiting/request-size limits; no pagination convention; no Whisper/Piper container wired into the compose stack (`:129-159`) |
| 21 | Open blockers | None block Phase 2D-B's *design* work; explicit user decision requested on Recommendation 10 (real-Postgres verification pass) before Phase 2D-B's own engines are *built* (`:583-587, 624`) |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | (a) A streaming-synthesis architectural fork was escalated to the user before being applied, then closed (`:68-70`). (b) API-consistency finding: `personality-engine`/`communication-engine` used bare, unprefixed URL paths rather than the established `/v1/<domain>/...` convention — surfaced explicitly, not silently normalized (`:253-261`; later fixed, per this project's own task record). (c) `communication-engine`'s `session_registry.py` is unbounded, single-process, in-memory state with no TTL/max-entry cap (`:163-169`). (d) Complexity outlier: `session_websocket` (`api/websocket.py`) graded **D (22)** by `radon cc`, the single most complex function introduced this phase (`:753, 758-765`). (e) Two new ADRs filed this phase (ADR-030, ADR-031), with an honest process note that ADR-030 was filed *after* both TDDs were approved rather than before, as originally committed (`:340-349`). |

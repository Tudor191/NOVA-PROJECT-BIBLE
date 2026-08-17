# Phase 2A — Project Health Snapshot

Source: `docs/roadmap/architecture-reviews/phase-2a-gate-review.md` (read in full for this snapshot; every value below is cited to a specific line).

| # | Field | Value |
|---|---|---|
| 1 | Phase identity | Phase 2A |
| 2 | Phase/Sub-Phase name | AI Model Orchestration Layer (AI Model Orchestration Engine) |
| 3 | Report date | **2026-08-05** (`:4`) |
| 4 | Branch | Not reported |
| 5 | PR number | No PR — direct commit workflow (git-history-derived; commit `70d034e` carries no PR reference) |
| 6 | Commit / merge commit | Not reported |
| 7 | Phase status | "**Go.**" (`:518`). Closing: "Phase 2A is closed. The Reasoning Engine Technical Design Document ... may now begin." (`:535-537`) |
| 8 | Production SLOC | **12,412** — application `src/` (12,189) + Alembic migrations (223) (`:564-567, 577`). Prior phase (1) baseline in the same table: 9,794. |
| 9 | Total SLOC | **38,541** (all tracked languages, all purposes), up from 30,946 (`:571`) |
| 10 | SLOC methodology/tool | `cloc`, `radon cc` + a direct `ast`-based script, `grimp`, `git ls-files`/`du`, `pytest --cov` (`:546-547`). **Note:** this phase's own measurement did not use the `--skip-uniqueness` flag Phase 1 and later Phase 2B used — see the master index's SLOC History section. |
| 11 | SLOC scope | Application `src/` + Alembic migrations (`:564-567`) |
| 12 | Test status | "**480 tests pass** across all 12 first-party packages (up from Phase 1's 376), zero failures. The new engine alone contributes 95 (60 unit, 15 integration, 20 ADR-023 connector-compliance)." (`:25-27`) |
| 13 | Test count | 480 (`:642`) |
| 14 | Coverage | No aggregate reported this phase — only the new engine's own figure: "84% (1,361 statements, 214 missed)" for `ai-model-orchestration-engine` (`:647`) |
| 15 | CI status | Ruff: PASS, 0 issues, whole repo. MyPy: PASS, 209 files across 12 packages. Import-linter: PASS, 4/4 contracts kept, 197 files / 899 deps (`:30-36, 648-650`) |
| 16 | Real-infrastructure status | "No Docker daemon in this development environment, confirmed directly again this session." No real-database verification performed this phase (`:113-118`) |
| 17 | Documentation health | Generated TypeScript client "was stale — 9 of this phase's 10 registered `ai_model_orchestration` payload types had no corresponding `.ts` file" — fixed this review, regenerated (33 → 42 files) (`:99-104`). Architecture documents: "89 total" (`:616`). |
| 18 | Architecture status | §15/§16 — same clean-compliance pattern as Phase 1: Dependency Inversion via `domain/ports.py` Protocols, Interface Segregation, Open/Closed via `connectors/factory.py`, Liskov substitution verified via the 20-test ADR-023 compliance suite (`:380-437`) |
| 19 | Security status | No hardcoded secrets, no raw SQL interpolation, `pip-audit` zero known vulnerabilities, no auth (same Phase-7-deferred rationale as Phase 1), no CORS/rate limiting, non-root Dockerfile, Pydantic validation. Notable positive finding: "API-key handling for the Anthropic connector is credential-absent-by-default" — `ConnectorFactory` raises rather than constructing with an empty credential (`:158-189`) |
| 20 | Unverified infrastructure | Five items carried forward unaddressed from Phase 1 (no Docker daemon, no drift check, no CORS/rate limiting, no admin API, no pagination convention). New-this-phase: budget enforcement exists as isolated, unit-tested pieces with no caller wiring them together — `ai_model.budget.exceeded` is "a contract-tested, publishable subject that nothing in the current codebase ever actually publishes." Only one real cloud connector (Anthropic) exists; robustness against a differently-shaped provider "remains unproven." (`:67-80, 106-132`) |
| 21 | Open blockers | None block Phase 2B's design work, except item 3's latency verification (`:509-513`) |
| 22 | Branch hygiene | Not reported |
| 23 | Notes / important findings | Two issues found and fixed during this review: the missing `ai_model.model.health_changed` outbox publish in `health_monitor_worker.py`, and the stale TypeScript client (`:92-104, 480-484`). 50,000 SLOC milestone: "12,412 / 50,000 ≈ 24.8%" (`:678`). |

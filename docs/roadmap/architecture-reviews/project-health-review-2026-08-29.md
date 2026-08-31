# Project Health Review — 2026-08-29 (the ~30,000 Production SLOC milestone)

**Trigger:** SAD 15 §10's **~30,000 Production SLOC reminder**, crossed and
surfaced by the [Phase 3E Gate Review](phase-3e-agent-os-gate-review.md) §12
as condition **C-5**. This document is that review, conducted at the user's
direction during the Phase 3E Gate Review closure pass.

**Repository state reviewed:** branch `phase-3e-agent-os`, verified code SHA
`60934ac07166acd3635e3bf33dee9462d97f8a04`. Every figure below was produced
by a command run in the session that wrote this document
([protocol](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md) §0.3.1/§0.3.3).

**Relationship to the 2026-08 review.** This is the **second** Project
Health Review. The [first](project-health-review-2026-08.md) was triggered
by the same threshold crossing at Phase 2D-B and is not superseded — its
findings stand as history. This one reviews what changed since, at the point
where Phase 3 has shipped the largest and most integrative sub-phase in the
project.

**Verdict: HEALTHY, with three findings and one systemic observation.** No
finding blocks Phase 3E. Two of the three findings are pre-existing defects
from Phase 1, reported here and deliberately not fixed
([protocol](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md) §13.1: newly
discovered defects outside the phase's scope are reported, not silently
fixed and not silently ignored).

---

## 0. Does this discharge the 50,000 SLOC Engineering Review Milestone?

**No — and that is stated plainly rather than claimed.** SAD 15 §10 allows a
30k-triggered review to satisfy the 50k gate "**provided its scope already
covers that milestone's twelve items**". This review addresses all twelve, but
three of them (**performance profiling**, and the runtime halves of
**database optimization** and **security**) cannot be genuinely executed in
this environment: there is no Docker daemon, no deployed stack, no load
generator, and no production telemetry. Those three are marked **Limited**
below with the reason.

**Therefore the 50,000 SLOC gate still applies independently when reached.**
Current Production SLOC is 34,446 (full scope) — the gate is not close, and
this review does not consume it.

---

## 1. The twelve Engineering Review Milestone items

| # | Item | Coverage | Result |
|---|---|---|---|
| 1 | Architecture audit | **Full** | §2 — no violation |
| 2 | Dependency audit | **Full** | §3 — zero known vulnerabilities |
| 3 | Performance profiling | **Limited** | §4 — no runtime environment; test-suite timings only |
| 4 | Security review | **Partial** | §5 — static and design review full; image scanning unavailable |
| 5 | Refactoring opportunities | **Full** | §6 — one candidate |
| 6 | Dead code analysis | **Full** | §7 — one systematic artifact |
| 7 | Duplicate code detection | **Full** | §8 — no material duplication |
| 8 | Technical debt review | **Full** | §9 — ledger of 11 items |
| 9 | Database optimization review | **Partial** | §10 — schema/migration structure full; query performance not measurable |
| 10 | Event Bus review | **Full** | §11 — **two findings** |
| 11 | API consistency review | **Full** | §12 — one naming observation |
| 12 | Documentation review | **Full** | §13 — healthy |

---

## 2. Architecture audit — PASS

```
uv run lint-imports
→ Analyzed 582 files, 2554 dependencies.
→ Contracts: 7 kept, 0 broken.
```

Seven import-boundary contracts hold across 582 files and 2,554 dependency
edges. The seventh (`nova-agent-sdk` has no engine-specific knowledge) was
added by Phase 3E and is the first contract governing `agent-os/`.

**Subsystem inventory, reconciled against the filesystem this pass:** 14
services · 3 `agent-os` components + 1 SDK · 5 Agent Packages · 8 shared
packages · 26 workspace packages · 24 ADRs · 15 Alembic migration chains ·
115 registered Event Bus payloads across 14 contract modules · 97 generated
TypeScript contract files.

**The layered discipline holds.** Every engine still separates
`domain/` (pure, framework-free) from `repository/`, `api/`, `events/` and
`clients/`, and `domain/` may import only `nova_contracts`, `nova_agent_sdk`
and sibling `domain/` modules. Phase 3E's four new `agent-os` components
follow the same shape without exception, which is why they slotted into the
existing import-linter contracts with one addition rather than a rewrite.

**No ADR has been falsified.** Eight were checked in both directions during
the Phase 3E Gate Review (§3 there); none required superseding, and no new
ADR was needed for the largest sub-phase in the project — a meaningful
signal that the Phase 1/2 architecture absorbed NAOS as designed.

---

## 3. Dependency audit — PASS

```
uv run pip-audit   → No known vulnerabilities found
pnpm audit --audit-level=high → No known vulnerabilities found
```

`pip-audit` additionally reports every local workspace package as "not found
on PyPI and could not be audited" — expected and correct: those are this
repository's own unpublished packages, not third-party dependencies. The
finding line is the one that matters, and it is clean.

**One dependency added by Phase 3E:** none. Phase 3E introduced no new
third-party dependency at all — it is built entirely from what Phases 1–3D
already brought in. (`jsonschema>=4.23` was Phase 3D's.)

---

## 4. Performance profiling — LIMITED

**Cannot be genuinely executed here.** No Docker daemon, no deployed stack,
no load generator, no production telemetry. Reporting the gap rather than
substituting a proxy for it ([protocol](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md)
§0.3.5).

What *can* be reported, as a weak signal only:

- Full uncached suite: **52/52 tasks, 1,646 tests, 1m2s wall clock.**
- Slowest package by far: `agent-os/kernel` at **37.68s** for 55 tests — it
  is the only package that spawns real `git` and `pytest` subprocesses.
- The real-Postgres acceptance E2E runs in **9.8–11.2s**, stable across 10
  consecutive runs.

**None of this is performance profiling of the running system**, and it must
not be cited as such. The system has never been run under load.

---

## 5. Security review — PARTIAL

**Full, and passing:**

- **ADR-032's identity-confidence gate is load-bearing and correct.** Phase
  3E's decision D6 exists precisely because the gate is real: passing an
  ephemeral `agent_instance_id` as `requested_by` resolved to confidence
  0.0 against an absent policy (threshold 1.0) and **denied every agent
  action**. The fix routes the real user id; agent provenance stays on
  `Action.source`. A gate that silently passed would have been the far worse
  outcome.
- **Sandbox containment is fail-closed.** D8: `TerminalAdapter` **refuses** a
  supplied `cwd` when no sandbox root is configured, rather than honouring
  it. D7 moved the anchor for relative paths without weakening the
  containment check — `../` traversal and symlink escape are still rejected.
- **The approval loop never auto-approves on timeout** (Phase 3D,
  re-verified as unchanged).
- **ADR-020 holds:** every model boundary in every Phase 3E test is a fake;
  `ai_model.generate.request` is the only model subject any `agent-os`
  component may publish.
- **Zero known dependency vulnerabilities** (§3).

**Limited, and disclosed:**

- **No container image scanning for `agent-os`.** No component has a
  Dockerfile, so Trivy has never scanned one. This is Gate Review condition
  **C-3**, ratified as a deferred deployment obligation.
- **No runtime security testing** — no penetration testing, no fuzzing, no
  runtime privilege audit. The system has never been deployed.
- **`nova-auth` does not exist.** Permission enforcement across
  `capability-engine`, `action-engine` and `agent-os/registry` is
  declared-intent-only — an accepted, thrice-disclosed architectural gap
  (TDD 3C §10, TDD 3D §7/§11, TDD 3E §5 item 5), not an oversight. It is the
  single largest known security gap in the project and should be the
  security-relevant headline of whichever phase builds it.

---

## 6. Refactoring opportunities — ONE CANDIDATE

Eight largest production source files:

| Lines | File |
|---|---|
| **1,498** | `ai-model-orchestration-engine/domain/router.py` |
| 658 | `reasoning-engine/domain/pipeline.py` |
| 561 | `agent-os/kernel/domain/scheduler.py` |
| 534 | `ai-model-orchestration-engine/main.py` |
| 516 | `action-engine/domain/pipeline.py` |
| 456 | `ai-model-orchestration-engine/domain/models.py` |
| 425 | `nova-contracts/__init__.py` |
| 416 | `agents/coding-agent/src/handler.py` |

**`router.py` at 1,498 lines is the one genuine outlier** — 2.3× the next
largest file, and 128% larger than the whole `agent-os/kernel` domain layer.
It has accreted across Phase 2A (routing), 2D-A (speech), and 2D-B
(biometric/wake modalities). Its 91% coverage is the lowest of any engine
touched recently.

**Recommendation: a candidate, not a defect.** Nothing about it is broken and
no test fails. If a future phase extends model orchestration again, splitting
the modality-specific routing paths out first is the cheap moment to do it.
**Not proposed for action now** — it is outside Phase 3E and refactoring a
working 1,500-line module with no failing test is how regressions get
introduced.

`nova-contracts/__init__.py` at 425 lines is a pure re-export barrel; its
length is a function of 115 payloads and is not complexity.

---

## 7. Dead code analysis — ONE SYSTEMATIC ARTIFACT

**12 `TODO` markers in production source. All twelve are the same scaffold
artifact**, in the same file, with the same text:

```
services/{action,capability,communication,knowledge,memory,perception,
          personality,planning,world-model}-engine/src/*/__init__.py
agent-os/{kernel,registry,supervisors}/src/*/__init__.py
→ """<Name>. TODO: one paragraph on responsibility and the Bible Part it implements."""
```

Both `tools/scaffold-engine.py` and `tools/scaffold-agent-os-component.py`
emit this placeholder, and no engine has ever filled it in. **Zero
`FIXME`/`XXX`/`HACK` markers anywhere.**

**This is a documentation-completeness gap, not dead code**, and it is
systematic rather than incidental — which makes it cheap to fix in one pass
and worth fixing at the scaffold template too, so engine #15 does not
inherit it.

**Five `raise NotImplementedError` sites, all legitimate** — inspected
individually, none is a stub: `execution_backend.py:172` and
`supervisors/domain/handler.py:56,61,74` are deliberate base-class/Protocol
raises with explanatory messages; `in_memory.py:183` guards an unsupported
backend operation.

---

## 8. Duplicate code detection — NO MATERIAL DUPLICATION

The structural risk in a 26-package monorepo is per-engine boilerplate, and
this project has already attacked it deliberately. Extractions A–E
(`docs/roadmap/architecture-reviews/step3-nova-service-kit-extraction-gate-review.md`,
`step3-extraction-e-gate-review.md`) pulled the four repeating shapes into
shared packages:

- `make_health_router()` — one health surface, 26 consumers
- `create_engine_and_session_factory()` — one engine/session bootstrap
- `dispatch_ready_events()` — **one** transactional-outbox dispatch loop,
  shared by every outbox-carrying engine
- `bind_event_bus()` — one Event Bus binding idiom
- `nova_contracts.entities` — shared domain types instead of per-engine copies

**Phase 3E consumed all five without adding a sixth variant** — its four
`agent-os` components reuse `make_health_router()` and `bind_event_bus()`
unmodified, and its two outbox-carrying engines drain through the shared
`dispatch_ready_events()`. That is the strongest available evidence the
extraction actually worked: the largest new subsystem in the project needed
no new shared abstraction.

The remaining repetition is per-engine `main.py` wiring — declarative,
intentionally explicit, and not worth abstracting further.

---

## 9. Technical debt review — 11 ITEMS, ALL DISCLOSED

No undisclosed debt was found. Every item below is already recorded in a
design document, a Gate Review, or a source docstring.

| # | Item | Where recorded | Severity |
|---|---|---|---|
| 1 | `nova-auth` does not exist; permissions declared-intent-only across three engines | TDD 3C §10, 3D §7/§11, 3E §5 | **High** — the project's largest security gap |
| 2 | `agent-os/*` not containerised, not scanned, not in compose | Gate Review C-3, TDD 3E §15 | Medium |
| 3 | `AgentContext` not pre-scoped (memory/knowledge/world-model all empty, `degraded=True` always) | `scheduler.py` docstring | Medium |
| 4 | Kernel Scheduler scoring not implemented | TDD 3E §4 (ratified) | Medium |
| 5 | `agent.<id>.<state>` + `agent_os.health.snapshot` unpublished | TDD 3E §10 (ratified) | Medium |
| 6 | `DecisionMemoryPort` is a structured-log stub | `supervisors/domain/ports.py` (ratified) | Low |
| 7 | `planning.goals.current` unfiltered by user (`task_graph` has no ownership column) | `planning-engine/domain/ports.py` | Medium |
| 8 | Registry uninstall does not exist; superseded rows permanent | doc 16 §5 | Low |
| 9 | 12 scaffold `TODO` placeholders (§7) | this review | Low |
| 10 | `router.py` at 1,498 lines (§6) | this review | Low |
| 11 | SLOC methodology Option A/B undecided | `project-health-master.md` §2 | Low |

**Debt is being disclosed at the point of creation rather than discovered
later** — items 3–8 were all written into source docstrings or design
documents by the slice that created them. That is the healthiest signal in
this review.

---

## 10. Database optimization review — PARTIAL

**Structure, full and passing.** 15 Alembic migration chains, one per
persistence-owning component:

```
13 services × 1 (communication-engine and digital-twin-engine × 2)
 2 agent-os components × 1  (kernel, registry)
```

**Every engine owns exactly one Postgres schema and writes no other's** —
the per-engine-schema discipline holds without exception, and it is what let
the Phase 3E real-Postgres E2E put **six engines' schemas in one database**
with no architectural change: every chain namespaces its `version_table`
(`alembic_version_<engine>`) and every `0001` uses `CREATE SCHEMA IF NOT
EXISTS`. That property was designed in early and paid off here.

**59 `real_infra` tests pass against real PostgreSQL 16.13** (Gate Review
§7), covering six engines' repository layers including both Phase 3E
components.

**Limited:** no query-plan analysis, no index-usage review, no connection-pool
tuning, no data-volume testing. There is no running database with
representative data to measure. The one scalability question worth carrying
forward is the one the 2026-08 review already raised and this review
re-confirms as still open: **outbox polling connections grow linearly with
engine count** — 15 chains now, each with its own Arq worker polling its own
outbox. Not urgent; worth revisiting at the 50k milestone.

---

## 11. Event Bus review — TWO FINDINGS

**Inventory:** 115 registered payloads across 14 contract modules; 88
distinct subjects declared across all engines' `published.py` /
`subscribed.py` allow-lists.

**Reconciliation of declared-vs-registered surfaced exactly five subjects
declared but not registered.** Three are globs and are correct by design:
`agent_os.instance.*.inbox`, `agent_os.task.*`, `perception.*.observed`.

**The other two are genuine defects:**

> **PHR-1 — `communication.intent.received` has a live subscriber and no
> registered payload.** `memory-engine` subscribes to it
> (`main.py:159`) and handles it (`events/handlers.py:93`), but no
> `@register_payload("communication.intent.received")` exists anywhere in
> `nova-contracts`. The handler therefore validates nothing on the wire.
>
> **PHR-2 — `perception.filesystem.observed` has a live subscriber and no
> registered payload.** `knowledge-engine` subscribes
> (`main.py:251`) and handles it, with the same absence.

**Both are pre-existing and outside Phase 3E.** Dated by `git log -S`:
`communication.intent.received` entered at `8257420` (2026-08-04, "Add Memory
Engine…") and `perception.filesystem.observed` at `298989d` (2026-08-04, "Add
Knowledge Engine…") — both **Phase 1**. Neither appears anywhere in the
Phase 3E commit range (`c6c6c59..HEAD`, searched with `git log -S`).

**Reported, not fixed.** Fixing them means adding two contract payloads and
their tests to engines Phase 3E does not touch — outside this phase's scope
and outside the closure pass's mandate. **Recommended as a small, separate
slice**, not folded into Phase 3E.

**Everything else reconciles.** Phase 3E's own additions — 10 new subjects
across `agent_os.*` and `planning.goals.current.*` — are all registered, all
contract-tested, and all present in the generated TypeScript with zero drift.

---

## 12. API consistency review — PASS, one observation

All 14 REST surfaces use the `/v1/<domain>` prefix convention without
exception:

```
/v1/action  /v1/capabilities  /v1/communication  /v1/decisions
/v1/digital-twin  /v1/executive  /v1/knowledge  /v1/memories
/v1/models  /v1/personality  /v1/plans  /v1/reasoning
/v1/usage  /v1/world
```

**Observation, not a defect:** the segment is inconsistently singular
(`/v1/action`, `/v1/reasoning`) versus plural (`/v1/capabilities`,
`/v1/memories`, `/v1/plans`, `/v1/decisions`), and two are abbreviated
(`/v1/world` for world-model, `/v1/executive` for executive-cognition).
Changing any of them now would be a **breaking API change** for no
functional gain, and
[`11-api-architecture.md` §6](../../architecture/11-api-architecture.md#6-backward-compatibility--deprecation-policy)'s
backward-compatibility policy correctly discourages it. **Recommendation:
leave as-is; fix the convention for new surfaces only.**

**`agent-os/*` deliberately exposes no `/v1` surface at all** — TDD 3E §4
gives the Kernel a health-only surface because its work is Event-Bus-driven.
That is a design decision, not an inconsistency.

---

## 13. Documentation review — HEALTHY

**Quantitative:** 1,646 tests against 33,759 production SLOC (src only) and
29,369 test SLOC — a **0.87:1 test-to-production ratio**, which for a system
with this much orchestration is strong.

**Structural health:**

- Every phase from 1 through 3E now has **both** a Gate Review and a
  23-field Project Health record — the pairing
  [`project-health/README.md`](../../project-health/README.md) requires. Phase
  3E's was the last missing one and was written this pass.
- `project-health-master.md` carries a complete per-phase timeline **and** a
  §2 SLOC-methodology history that honestly records nine tool/scope changes
  and refuses to merge them into one trend. That section is the single best
  artifact in the documentation set: it makes a genuinely messy history
  legible instead of hiding it.
- The [completion protocol](../../PROJECT_PHASE_COMPLETION_PROTOCOL.md),
  established 2026-08-29, is now the standing gate for every phase closure.
  This review is one of its outputs.

**The one live structural gap:** `docs/design/phase-3/` still has **no
`README.md`**, unlike every earlier phase package (`phase-1/` through
`phase-2d/` all have one). The protocol itself flags this at §6.1. Phase 3's
design package now holds 18 documents and is the largest in the project — the
one most in need of an index. **Recommended for the Phase 3 closure**, not
Phase 3E's (3E is a sub-phase; the package README belongs to the parent).

---

## 14. Findings summary

| ID | Finding | Severity | Scope | Action |
|---|---|---|---|---|
| **PHR-1** | `communication.intent.received` — live subscriber, no registered payload | **Medium** | Pre-existing, Phase 1 | Reported, not fixed. Separate slice. |
| **PHR-2** | `perception.filesystem.observed` — live subscriber, no registered payload | **Medium** | Pre-existing, Phase 1 | Reported, not fixed. Separate slice. |
| **PHR-3** | 12 scaffold `TODO` placeholders in `__init__.py`, plus both scaffold templates that emit them | **Low** | Pre-existing, systematic | Reported. Cheap one-pass fix + template fix. |
| **PHR-4** *(observation)* | `router.py` at 1,498 lines | **Low** | Pre-existing | No action now; split when next extended. |

**No finding blocks Phase 3E**, and none is a regression introduced by it.

---

## 15. Overall assessment

**The codebase is healthy at 34,446 Production SLOC.** The evidence for that
is not the absence of findings — it is the shape of them.

Phase 3E added the most integrative subsystem in the project: an agent
operating system, five agent packages, a supervisor, and a real end-to-end
path that runs a coding task through seven engines to a real git commit. It
did so with **no new third-party dependency, no new shared abstraction, no
new ADR, one new import-linter contract, and no falsified ADR**. A codebase
that absorbs that much new surface without needing to change its own
foundations is one whose foundations are holding.

The three real findings are all **pre-existing**, all **low or medium**, and
two of them are the same class of defect from the same week in Phase 1 —
which says the contract-registration discipline tightened after Phase 1 and
has held since.

The most valuable habit visible in this review is **disclosure at the point
of creation**: six of the eleven technical-debt items were written into
source docstrings by the slice that created them, before any reviewer asked.
That is why this review found so little that was hidden — most of it was
already written down.

**The one thing to watch** is item 1: `nova-auth` still does not exist, and
three engines now depend on declared-intent-only permission enforcement. That
gap has been correctly disclosed three separate times, which is the right
handling — but it has also now been deferred three times, and Phase 3E made
it materially larger by adding agents that execute real filesystem, terminal
and git actions. It should be the security headline of whichever phase builds
it, and it should not be deferred a fourth time without an explicit decision.

**Recommendation: proceed.** The ~30,000 reminder is discharged by this
document. Feature development is not paused, and the ~50,000 gate remains
independently in force (§0).

---

**Reviewed:** 2026-08-29 · **Branch:** `phase-3e-agent-os` ·
**Verified code SHA:** `60934ac07166acd3635e3bf33dee9462d97f8a04` ·
**Trigger:** SAD 15 §10 ~30k reminder · **Verdict:** HEALTHY ·
**50k gate:** not discharged, still independently in force

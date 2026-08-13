# Phase 3 — TDD Preparation & Fork Resolutions

**Status: research and design-decision preparation only. No production code was
written or modified during this pass, and no Phase 3 TDD is authorized to begin
until the user explicitly approves the fork resolutions and TDD scope proposed
below.** This document builds directly on `00-research-and-scope.md` (the prior
research pass) — where this document narrows or corrects a finding from that
pass, it says so explicitly rather than silently superseding it.

Three parallel deep-research passes (NAOS/agent-os workspace & scaffolding;
Planning/Action/Capability + contract-ownership precedent; reasoning-engine
Level 3/4 + documentation discrepancies + frontend precedent) plus direct
primary-source verification of the approval-flow and frontend-architecture
documents are consolidated here. Every claim is sourced to an exact file and
line range.

---

## 0. Phase 2D-D closure status — reconfirmed, unchanged

**Still not formally closed.** Checked again at the start of this pass via
`mcp__github__actions_list`: the five most recent `real-infra-checks.yml` runs
on `claude/new-session-e1cseg` are:

| Run ID | Conclusion | Head commit | Event | Date |
|---|---|---|---|---|
| 31671523896 | failure | `cd44be0` (pre-fix) | schedule | 2026-08-13T05:47:18Z |
| 31567543681 | failure | `cd44be0` | schedule | 2026-08-12T05:44:29Z |
| 31461343807 | **success** | `9a812​38d` | schedule | 2026-08-11T05:20:55Z |
| 31359464265 | failure | `cce5626` | schedule | 2026-08-10T05:42:46Z |
| 31296349533 | failure | `744eb7a` | schedule | 2026-08-09T05:16:58Z |

**No run has yet fired against the Step 10 fix commit (`812faf0`), the Gate
Review commit (`d57db18`), or the Phase 3 research commit (`fcc60d4`).** The
next nightly `schedule` firing is the earliest opportunity for confirmation.
The previously-scheduled follow-up check-in (`trig_017217PxboYqA39zERzUTATJ`,
~2026-08-14T07:44Z) remains the mechanism for catching that run.

**Per explicit instruction, this remains binding: Phase 2D-D is not closed, and
no Phase 3 implementation is authorized until real-infrastructure evidence
confirms the fix.** Everything below is preparation only.

---

## 1. Phase 3 scope and architecture review

### 1.1 Canonical scope, unchanged from the prior research pass

`docs/roadmap/ENGINEERING_ROADMAP.md:503-548` remains the scope boundary
(quoted in full in `00-research-and-scope.md` §1.1). Per user decision 10,
this roadmap section — not Bible Parts 04/09/12/15's full eventual vision —
is authoritative for what Phase 3 delivers.

### 1.2 What this pass adds to that picture

Three things materially sharpen the prior pass's scope understanding:

1. **`docs/architecture/02-repository-and-folder-structure.md` already
   contains a full target blueprint** for `agent-os/` and `agents/` — not
   just ADR-008's prose decision. This is now the primary reference for
   workspace/scaffolding work (§5).
2. **The approval-gate question (Fork E2) has a concrete, named,
   already-documented event flow** (`autonomy.approval.requested` /
   `autonomy.decision.made`, owned by `autonomy-engine`) that Phase 3 cannot
   literally use, since `autonomy-engine` doesn't exist until Phase 4. This
   is sharper and more concrete than the prior pass's doc-13-§7-only framing.
3. **`apps/web-client`'s Phase 3 line item ("Planning + Agent Activity panels
   added") presupposes a base web-client shell, `api-gateway`, and
   `ws-gateway` that were nominally a *Phase 2D* deliverable
   (`ENGINEERING_ROADMAP.md:450-452`) and were never built.** This is a new,
   previously-undetected discrepancy (§11) with real scope consequences
   for the TDD split (§7) and prerequisites (§6).

### 1.3 Confirmation of the 10 approved architectural decisions against evidence

| # | User's decision | Evidence found this pass |
|---|---|---|
| 1 | Split TDDs 3A-3E | Confirmed as the only precedent-consistent approach (§7). |
| 2 | Action Engine implements the full approval loop alone | Confirmed as roadmap-mandated (`ENGINEERING_ROADMAP.md:544`); the *mechanism* needed sharper resolution — see Fork E2 (§2.2). |
| 3 | Lighter OS-level sandboxing, no gVisor/Firecracker in Phase 3 | Confirmed consistent with doc 12 §8's `container` backend being Phase 7+ (§2.3). |
| 4 | No arbitrary frontend tech decision — research first | Research found this is **already fully documented**, not an open choice — see Fork E4 (§2.4). |
| 5 | Pull recursion trigger forward | Confirmed independently implementable — exact code location identified (§2.5). |
| 6 | Keep GoalsPort RPC migration late | Confirmed — depends on `planning-engine` existing. |
| 7 | `agent-os/` as new top-level pillar, doc 12/ADR-008 authoritative | Confirmed; doc 02 already specifies the exact target tree (§5.1). |
| 8 | ADR-005/032 compliance, communication only through the established boundary | Confirmed binding; ADR-032's exact requirements quoted in full (§2.2, §12 of prior doc). |
| 9 | Autonomy Engine explicitly out of Phase 3 | Confirmed; this is precisely why Fork E2's mechanism question is real (§2.2). |
| 10 | Roadmap scope boundary, not full Bible vision | Confirmed; reaffirmed by this pass's own discovery that Bible Part 12 doesn't even contain the risk-tier scale doc 13 attributes to it (§3.4). |

---

## 2. Decision matrix — Forks E1-E6

Each fork below follows the requested format: evidence, options, recommendation
(already given by the user where a decision was made), classification of what
changes, prerequisites, and existing-vs-proposed architecture distinction.

### Fork E1 — Combined Phase 3 TDD, or split by component?

**Evidence.** Every prior multi-engine phase in this project split into
sub-phase TDDs once complexity crossed a threshold (Phase 2D → 2D-A/B/C/D,
each with its own TDD and Gate Review). The roadmap's own complexity note
(`ENGINEERING_ROADMAP.md:523`) states Phase 3 "integrates the most engines
simultaneously" of any phase to date.

**Options.** A) Split into sub-phase TDDs. B) One combined TDD.

**User decision: Option A.** No new evidence this pass changes that
conclusion — if anything, the newly-discovered `apps/web-client`/gateway gap
(§11) makes a single combined TDD less workable, not more, since it adds a
genuinely separate, cross-cutting concern (frontend + gateway bring-up) that
does not share dependencies with the engine-sequenced work.

**What this decision changes.** Scope and dependency direction only — it is
a project-management/documentation-structure decision, not an architectural
one. No contracts, ownership, persistence, or security implications.

**Prerequisite.** None beyond agreeing the exact split (§7).

**Existing vs. proposed.** Entirely proposed — no existing Phase 3 TDD
exists to split.

---

### Fork E2 — Action Engine's Critical-risk approval gate without Autonomy Engine

**Evidence — sharper than the prior pass found.**

1. `docs/architecture/10-inter-engine-communication.md:87` (canonical
   event-flow table, row 8): *"Action carries risk | action-engine →
   `autonomy.approval.requested` | autonomy-engine evaluates Autonomy
   Level/Trust/Policy, replies `autonomy.decision.made`; if approval
   required, communication-engine prompts the user | Part 14 'Approval
   Workflows'"*.
2. Same document, §3 sync/async table (`:111`): *"Autonomy approval check
   before execution | Request/Reply | No timeout bypass — action blocks
   until a decision or explicit user timeout policy fires."*
3. `docs/architecture/11-api-architecture.md:55`: `POST
   /v1/autonomy/approvals/{id}/decide # approve/reject a pending autonomous
   action` — the approval-decision REST endpoint is explicitly namespaced
   under `/v1/autonomy/...`, i.e. owned by `autonomy-engine`.
4. `docs/architecture/13-auth-and-security.md:94-98` — the two-engine
   defense-in-depth model (already known from the prior pass), but this
   pass confirms **it names no communication mechanism at all** — it states
   only the *what* (`action-engine` classifies, `autonomy-engine`
   re-checks), never the *how* of soliciting/collecting approval.
5. `docs/bible/part-14-autonomy-engine.md:411-443` — "APPROVAL WORKFLOWS" is
   a Part 14 (Autonomy Engine) concept in the Bible itself, not a Part 12
   (Action Engine) one: *"Deployment requested. ↓ Generate execution plan.
   ↓ Present risks. ↓ Request approval. ↓ Execute. ↓ Verify. ↓ Report."*
6. `docs/roadmap/ENGINEERING_ROADMAP.md:544` (Phase 3 acceptance criteria,
   already known): a working approval gate is explicitly required **in
   Phase 3 itself**, "ahead of the full Autonomy Engine (Phase 4) providing
   the policy layer around it."
7. **New finding: no existing "ask the user something and route the reply
   back to the original requesting engine" mechanism exists anywhere in
   this codebase.** `services/communication-engine/src/nova_communication_engine/domain/clarification.py`
   (the only clarification-adjacent module that exists) is explicitly
   scoped to addressee-ambiguity only (its own docstring: *"General
   content-level clarification (Reasoning Engine asking the user for more
   information...) is explicitly out of this phase's scope"*).
   `ConversationSession.pending_questions` (`domain/models.py:156-157`)
   carries no requester-identity or correlation metadata back to an
   external engine — it is a pure communication-engine-internal display
   concept.

**The genuine tension, stated precisely.** The roadmap demands a real,
working, blocks-until-decided approval gate in Phase 3 (evidence 6). The
*only* already-documented mechanism for that exact behavior is
`autonomy.approval.requested`/`autonomy.decision.made`, explicitly owned by
`autonomy-engine` (evidence 1-3) — which, per user decision 9, must stay out
of Phase 3. Neither doc 13 nor any other document specifies a fallback
mechanism for a Phase-3-only, `autonomy-engine`-free version of this flow
(evidence 4, 7).

**Options, restated with the sharper evidence.**

- **Option A (user-approved).** `action-engine` implements a
  self-contained approval loop using **new, Phase-3-scoped event subjects**
  it defines and owns itself (e.g. `action.approval.requested` /
  `action.approval.decided` — exact names are a TDD 3D decision, not fixed
  here) — never reusing or pre-defining `autonomy.approval.requested`/
  `autonomy.decision.made`, which stay reserved, undefined, for
  `autonomy-engine` to claim in Phase 4. The prompt itself still goes out
  through the existing, unmodified `communication.intent.deliver.request`
  gate (ADR-005-compliant — `action-engine` never publishes
  `communication.intent.*` directly). Since no reply-routing mechanism
  exists yet, and `api-gateway` does not exist (§11), the decision-collection
  side is most consistent with this repo's own existing precedent
  (communication-engine, personality-engine, digital-twin-engine, and
  perception-engine all already expose their own direct `/v1/<domain>/...`
  REST surfaces, normalized under task #92, consumed directly today because
  no gateway exists) — `action-engine` exposing its own
  `POST /v1/action/approvals/{id}/decide` endpoint (mirroring doc 11's
  naming convention for the reserved autonomy-engine path) is the
  lowest-risk, precedent-consistent stopgap, to be fronted by `api-gateway`
  once that service is eventually built (additive, not a redesign).
- **Option B.** Defer any real approval gate to Phase 4, ship only risk
  *classification* in Phase 3, explicitly disclosed as partial.

**User decision: Option A**, now with the concrete mechanism above spelled
out as the recommended TDD 3D design starting point (not fixed — TDD 3D
must still finalize exact subject names and the decision-record persistence
shape, following the `ProactiveDeliveryRecord` precedent from Phase 2D-D
Fork D for "new persisted record type discovered during implementation,
disclosed rather than silently added").

**What this decision changes.**
- **Contracts:** yes — new `action.approval.*` event subjects in
  `nova-contracts`, defined and owned by `action-engine`, not by any future
  `autonomy-engine` namespace.
- **Ownership:** `action-engine` owns the full approval decision for Phase
  3; this ownership is explicitly temporary/additive — Phase 4's
  `autonomy-engine` layers a *second*, independent check on top per doc
  13 §7's two-engine model, never replacing `action-engine`'s own check.
- **Persistence:** yes — `action-engine` needs its own pending-approval
  record (persisted, since "blocks until a decision" must survive a
  restart per the general per-engine-schema convention).
- **Security:** yes — this *is* the security-relevant mechanism; ADR-032
  applies directly (identity-confidence gating on who may decide).
- **Dependency direction:** none new — `action-engine` already depends on
  `communication-engine`'s existing gate (no new upstream dependency).
- **Scope:** contained to `action-engine`'s own TDD (3D).

**Prerequisite.** None blocking — this can be designed and built entirely
within TDD 3D without `autonomy-engine` or `api-gateway` existing, using the
stopgap-REST precedent above.

**Existing vs. proposed.** The two-engine defense-in-depth *principle*
(doc 13 §7) and the roadmap's acceptance criterion are existing,
authoritative constraints. The concrete `action.approval.*` subject
design, the pending-approval persistence shape, and the stopgap REST
endpoint are entirely proposed by this document, for TDD 3D to finalize.

---

### Fork E3 — Capability sandboxing depth in Phase 3

**Evidence**, largely as found in the prior pass, reconfirmed:
`docs/architecture/13-auth-and-security.md:90-92` names gVisor/Firecracker
generally; `docs/architecture/12-agent-architecture.md:265-270` (§8's
execution-backend table) places the `container` backend (the same
isolation technology) at Phase 7+; `ENGINEERING_ROADMAP.md:536`'s Phase 3
testing-strategy line asks only for *"sandboxed capability execution tests
proving no capability can escape its declared permission scope"* — a
permission-boundary claim, not an isolation-technology claim.

**Options.** A) Lighter OS-level permission/resource scoping in Phase 3,
gVisor/Firecracker deferred to Phase 7+. B) Full gVisor/Firecracker in
Phase 3.

**User decision: Option A.** Confirmed as the only option consistent with
doc 12 §15's own extension-point discipline — nothing new this pass
contradicts it.

**What this decision changes.**
- **Security:** yes — Phase 3's sandbox is a real but narrower boundary
  (permission/resource scoping only) than the Bible's eventual vision.
  This must be disclosed explicitly in TDD 3C, not silently implied to be
  full isolation.
- **Infrastructure:** avoids a genuinely new, heavyweight infra dependency
  (gVisor/Firecracker) this project has never needed before.
- **Contracts/ownership/persistence/dependency direction:** unaffected.

**Prerequisite.** None.

**Existing vs. proposed.** The Phase 7+ gVisor/Firecracker timeline is
existing (doc 12 §8). The specific lighter-weight Phase 3 mechanism (exact
OS-level primitives — e.g. restricted subprocess execution, filesystem/
network scoping) is entirely proposed, left to TDD 3C.

---

### Fork E4 — `apps/web-client` technology choice

**This is not an open architectural fork. It is fully resolved by existing
documentation that the prior research pass missed entirely.** Presenting
the evidence in full, per the user's explicit instruction to research
before deciding rather than choosing arbitrarily.

**Evidence — two independent, mutually-consistent governing documents:**

1. `docs/architecture/01-technology-stack.md:58-67` ("Frontend Stack"
   table), verbatim key rows:
   - *"Framework | **React 18** + **TypeScript 5** | Concurrent rendering
     suits a UI that must stay live/animated... while streaming dozens of
     independent real-time widgets."*
   - *"Build tool | **Vite**"*
   - *"State/data layer | **TanStack Query** (server state) + **Zustand**
     (UI/local state)"*
   - *"Real-time transport | **WebSocket** (primary) with **SSE** fallback,
     both fed by a `ws-gateway` service that bridges the Event Bus to the
     browser"*
   - *"Visualization | **D3.js** for graphs/timelines... **Framer Motion**
     for the living/idle animations"*
   - *"Design system | Internal `@nova/ui` package, Tailwind CSS + CSS
     variables for theming"*
2. `docs/architecture/04-frontend-architecture.md` (full file, 102 lines) —
   an entire dedicated frontend-architecture document, specifying the exact
   `apps/web-client/src/{app,panels,entities,realtime,shared}` directory
   layout, one `panels/` subdirectory per Bible-named dashboard (including
   `planning/` and `agents/` — exactly Phase 3's two named panels), state
   management split (TanStack Query / Zustand / React Hook Form+zod / a
   `useSession()` auth hook), accessibility (WCAG 2.1 AA), and performance
   targets.
3. `docs/architecture/00-overview-and-decisions.md:174` (ADR-003): *"Web &
   Desktop UI: TypeScript, React, Tauri (Rust shell)."*
4. `docs/architecture/02-repository-and-folder-structure.md:29-30`:
   `apps/web-client/ # React web command center`.
5. `docs/architecture/05-desktop-architecture.md:36-38`: the desktop app
   reuses `apps/web-client` verbatim inside a Tauri shell — one React app,
   two hosts.
6. No ADR discusses frontend/UI/BFF/gateway pattern at all (confirmed via
   exhaustive grep across all 24 ADR files) — the governing layer is docs
   01/04/09/11, not an ADR, which is why the prior pass (which searched
   ADRs and the Bible but not doc 01/04 specifically) concluded "no
   precedent found."

**Correction to the prior research pass.** `00-research-and-scope.md:855-872`
("Fork 4") stated *"this is a technology-choice fork with no governing ADR
or Bible guidance found in this research pass; it should be raised
explicitly rather than defaulted."* That conclusion was **incomplete, not
wrong in spirit** — the prior pass correctly found no ADR or Bible guidance,
but did not check doc 01 §6 or doc 04, which do settle it. Flagging this
per the standing discipline of not silently correcting a predecessor
document without saying so.

**Resolution: adopt the documented stack as-is.** React 18 + TypeScript 5
+ Vite + TanStack Router/Query + Zustand + React Hook Form/zod + Framer
Motion + D3.js + Tailwind/`@nova/ui`, read path via `ws-gateway`
(WebSocket, Event Bus bridge), write path via `api-gateway` (REST/BFF).
No technology decision is required from the user — the decision was
already made at the architecture-doc layer, before this session began.

**What this "decision" changes.** Nothing new — it confirms existing
documentation. However, see §11 for the real, newly-discovered gap this
fork's resolution surfaces: the infrastructure this stack depends on
(`api-gateway`, `ws-gateway`, the base `apps/web-client` shell) does not
exist, despite being nominally a Phase 2D deliverable.

**Prerequisite.** None for the technology choice itself. See §6 for the
`api-gateway`/`ws-gateway`/base-shell prerequisite this resolution surfaces.

**Existing vs. proposed.** Entirely existing — docs 01 §6, 04, ADR-003,
doc 02, doc 05 all predate this session's Phase 3 work.

---

### Fork E5 — Sequencing reasoning-engine's Level 3-4 completion

**Evidence — now with the exact code location and a discovered internal
inconsistency.**

`services/reasoning-engine/src/nova_reasoning_engine/domain/modes/__init__.py:53-84`
(`resolve_mode_and_level`) already dispatches `reasoning_level_hint` 3→
`STRATEGIC`, ≥4→`MULTI_STEP`, with `MULTI_STEP` fully wired as a real,
selectable `ModeConfig` (`modes/multi_step.py`) — **not** stubbed, **not**
raising `NotImplementedModeError` (that treatment is reserved solely for
`ReasoningMode.COLLABORATIVE`, `modes/__init__.py:45-49`). What's actually
missing is narrow and precisely located:
`MultiStepConfig.max_depth`/`parent_process_id` (`domain/models.py:297-301,367`)
are set but **never read anywhere in `pipeline.py`** — confirmed by grep,
the only two occurrences of `max_step_depth` in the whole engine are the
field declaration and the one assignment in `multi_step.py:22`.
`pipeline.py`'s `run()` has exactly one mode-specific branch in the entire
function (`if mode is ReasoningMode.REACTIVE:`, line 213); implementing the
recursion trigger means adding an analogous
`if mode is ReasoningMode.MULTI_STEP:` branch that reads `max_step_depth`,
detects an unresolved sub-question, recurses up to the depth cap, threads
`parent_process_id`, and aggregates confidence as the chain **minimum**
(per `multi_step.py`'s own docstring) — none of which exists today.

**Discovered internal inconsistency, worth flagging (see also §9.3).** The
Phase 2B gate review contradicts itself on reachability:
`phase-2b-gate-review.md:75-79` (§2) says *"nothing routes to [Multi-step]
by default at Level 4 **unless**... the heuristic falls through to it"*,
but `phase-2b-gate-review.md:269-275` (§9) claims the heuristic
*"never resolves to Multi-step... from a fresh objective"* **without** an
explicit hint. The actual code (`resolve_mode_and_level`'s final line,
`return ReasoningMode.MULTI_STEP, level`) is reachable with only
`reasoning_level_hint=4` and no other hint — no explicit
`reasoning_mode_hint` required. §9's claim is not accurate against the
code as it exists today; §2's framing is the correct one. Not correcting
the gate review now, per instruction — flagged here as a discrepancy.

**The explicit, stated trigger condition** (`phase-2b-gate-review.md:557-561`,
item 9): *"Implement Multi-step mode's recursion trigger... once a real
caller exercises Level 3/4 requests that plausibly need it."* No further
technical specification exists anywhere — it is genuinely undesigned, not
dormant-but-hidden.

**Options.** A) Split: recursion trigger early/independent (no
`planning-engine` dependency); `GoalsPort` RPC migration last (once
`planning-engine` exists). B) Keep as one undivided unit at the end.

**User decision: Option A**, confirmed independently implementable with
zero new-engine dependencies — the recursion trigger touches only
`pipeline.py` and existing `domain/models.py` fields already present in
reasoning-engine.

**What this decision changes.** Scope/sequencing only. No contracts,
ownership, persistence, security, or dependency-direction changes — this
is closing a self-contained Phase 2B gap inside an engine that already
exists, using fields already defined.

**Prerequisite.** None — can start immediately, independent of any other
Phase 3 TDD, including before Phase 2D-D's real-infra confirmation lands
(though per standing discipline, still gated behind that per §0).

**Existing vs. proposed.** The gap and its exact location are existing
facts (Phase 2B gate review, current code). The recursion algorithm itself
(depth-cap loop shape, sub-question detection heuristic) is entirely
proposed, left to whichever TDD slice implements it (recommended: TDD 3A,
see §7).

---

### Fork E6 — Doc 06 §3's stale "Agent Orchestrator" wording

**Evidence.** `docs/architecture/06-ai-layer-architecture.md:108-109`
(the only occurrence in the entire file, confirmed by full-file grep) still
reads *"Independent nodes... are dispatched to the Agent Orchestrator in
parallel."* Doc 12's status note (`12-agent-architecture.md:3-10`) states
doc 12 *"supersedes the v1 'Agent Orchestrator as one more engine'
design."* Doc 06 does link to doc 12 elsewhere (`06-ai-layer-architecture.md:69`,
inside the Reasoning Levels table's Level 4 row).

**Substance-conflict check (new this pass).** Doc 06 §3's one-sentence
description (independent Task Graph nodes dispatched in parallel) is a
strict subset of, and fully consistent with, doc 12 §7's Kernel Scheduler
description (*"Parallel dispatch. Independent Task Graph nodes are
scheduled simultaneously... Matches a `TaskNode.assigned_agent_category`...
to a concrete, healthy, versioned agent instance"*). **This confirms: it is
purely a naming/terminology gap, not a substance conflict** — doc 06 claims
no responsibility for "Agent Orchestrator" that doc 12's Agent Kernel
contradicts or omits.

**Options.** A) Fix as a trivial one-line correction alongside whichever
Phase 3 sub-phase TDD first cites doc 06 §3. B) Leave as-is until Phase 3's
own TDD naturally supersedes it.

**User instruction: document the discrepancy and its proposed resolution,
do not correct it now** unless a specific approved TDD requires the
correction. Recommendation stands: Option A, timed to TDD 3B
(`planning-engine`, which is the TDD that will actually cite and depend on
doc 06 §3's `TaskNode`/`TaskGraph` model).

**What this decision changes.** Documentation only — zero code/contract/
ownership impact either way.

**Prerequisite.** None.

**Existing vs. proposed.** The stale wording is existing. The fix timing
recommendation is proposed.

---

## 3. Discrepancy investigations (per explicit request, not silently resolved)

### 3.1 Doc 06's stale "Agent Orchestrator" terminology vs. NAOS (Doc 12)

Covered in full under Fork E6 (§2.6). Conclusion: terminology gap, not a
substance conflict. Proposed resolution: fix alongside TDD 3B, not now.

### 3.2 reasoning-engine's existing Level 3/4 dispatch vs. roadmap wording

Covered in full under Fork E5 (§2.5), including the newly-discovered
internal self-contradiction in the Phase 2B gate review (§2/§9 disagree on
whether Multi-step is reachable without an explicit hint). **Proposed
resolution:** no document correction needed now; TDD 3A's own text should
state the accurate reachability fact (§2's framing is correct: Multi-step
*is* reachable via `reasoning_level_hint=4` fallthrough with no explicit
mode hint) rather than repeating gate review §9's inaccurate claim.

### 3.3 Absence of Phase 3 coverage in Doc 20

**Evidence, confirmed and extended this pass.**
`docs/architecture/20-engine-responsibility-boundaries.md:3-14` states its
own scope explicitly: *"Written on completion of Phase 1 (the first three
engines built)... Sections 1-5 answer that question for the three engines
that exist today."* Full-document grep confirms: zero occurrences of
"Capability," "NAOS," or "agent-os"; "Action"/"Agent" appear only
incidentally (a Neo4j graph label, an event name, and the one already-known
`:98-99` diagram box labeled *"Action / Agent OS (later phases)"*); "Phase 3"
does not occur anywhere in the file. The document is **silent**, not
**explicitly exclusionary** — it simply never claims Phase 3 territory.

**The actual canonical Phase-3-relevant boundary document, confirmed and
quoted in full this pass:** `docs/design/phase-2c/00-executive-cognition-engine.md`
§5.7-§5.10 (`:557-622`). This section is executive-cognition-engine's own
TDD, written during Phase 2C, stating its boundary with three
not-yet-built Phase 3 components explicitly, in advance:

- **§5.9 (Future Planning Engine, `:597-608`):** *"once Planning Engine
  ships, this engine's `GoalsPort` moves from a caller-supplied placeholder
  to a real RPC-backed port... this engine will consume Planning Engine's
  goal hierarchy... as a read-only input to priority scoring... it will
  never decompose or modify that hierarchy itself."*
- **§5.10 (Future Action Engine, `:610-622`):** *"once Action Engine and
  `agent-os/kernel` ship, this engine's Cognitive Priority Matrix becomes
  one direct input to the Kernel Scheduler's own dispatch decision...
  This engine will never itself spawn, message, or supervise an agent
  instance — that remains `agent-os/kernel`'s job."*

**Proposed resolution:** no correction needed to doc 20 — it was never
meant to cover Phase 3, and does not falsely claim to. TDD 3E (agent-os,
where executive-cognition-engine's Cognitive Priority Matrix actually gets
wired into the Kernel Scheduler) should cite `phase-2c/00-executive-cognition-engine.md`
§5.9-§5.10 as its own governing boundary document, not doc 20.

### 3.4 Relationship between the Phase 3 roadmap and Bible Parts 04/09/12/15

Reconfirmed from the prior pass (roadmap delivers a deliberately narrower
slice of each Bible part), **plus two new, concrete findings this pass
surfaced:**

1. **A genuine Bible cross-attribution error.**
   `docs/architecture/13-auth-and-security.md:94` writes *"Action Engine's
   risk classification (Negligible → Critical, Part 12)"* — but Part 12
   (`docs/bible/part-12-action-engine.md`) **never names this five-tier
   scale anywhere in the file.** Its own "SAFETY LAYERS" section
   (`:453-471`) names only example operations requiring protection, no
   tier scale. The actual "Negligible / Low / Moderate / High / Critical"
   scale (note: **"Moderate," not "Medium"**) is defined in
   **`docs/bible/part-14-autonomy-engine.md:267-281`** ("RISK
   CLASSIFICATION"), i.e. Autonomy Engine's Bible part, not Action
   Engine's. This is a real documentation error (doc 13 misattributes a
   Part 14 concept to Part 12), independent of any Phase-3-vs-Bible
   scoping question. **Proposed resolution:** correct doc 13's citation
   from "Part 12" to "Part 14" — a one-line fix, deferred to whichever TDD
   (3D, action-engine) first needs to cite the risk scale accurately, not
   corrected now.
2. **Bible Part 04's formal agent-category names don't all match the
   roadmap's 5 chosen agent-package names.** Grep of Part 04's own
   "AGENT CATEGORIES" list (`part-04-multi-agent-intelligence-system.md:241-626`)
   against the roadmap's `research-agent`, `coding-agent`, `qa-agent`,
   `architect-agent`, `documentation-agent` (`ENGINEERING_ROADMAP.md:514`):
   only **`research-agent`** and **`coding-agent`** match a formal Part 04
   category header exactly ("Research Agent," "Coding Agent"). **`qa-agent`**
   maps to "Quality Assurance Agent" (formal header) with "QA Agent" only
   as informal prose shorthand. **`architect-agent`** maps to "Software
   Architect Agent" (formal header, drops "Software"). **`documentation-agent`**
   has **no formal Part 04 category header at all** — it exists in the
   Bible only as a `TEMPORARY AGENTS` example (`:647`) and workflow-prose
   shorthand (`:667`), not a named category. **Proposed resolution:** none
   needed — this is a naming-convenience choice already made at the
   roadmap/doc-02 layer (doc 02's own target `agents/` listing already
   uses `documentation-agent`, `02-repository-and-folder-structure.md:82`),
   consistent between roadmap and doc 02; only the Bible's own formal-list
   wording is looser/inconsistent internally (it uses "Documentation
   Agent," "QA Agent," "Architecture Agent," and "Software Architect"
   interchangeably in different prose passages). No document needs
   correction — flagging so the TDD author doesn't mistake the absence of
   a formal Bible header for a scope question.

---

## 4. What Phase 3 touches — reconfirmed, one addition

Unchanged from `00-research-and-scope.md` §5, **plus**: `apps/web-client`'s
Phase 3 slice now known to require `api-gateway` and `ws-gateway` bring-up
first (§6, §11) — these were not previously counted as Phase-3-touched
infrastructure since they were (incorrectly, per the roadmap's own text)
assumed already built from Phase 2D.

---

## 5. Required workspace/scaffolding changes

### 5.1 `agent-os/` and `agents/` as new top-level pillars

`docs/architecture/02-repository-and-folder-structure.md:53-83` already
specifies the exact target tree:

```
agent-os/
├── kernel/          # process manager, scheduler, supervision trees, health monitor
├── registry/        # discovery, install pipeline, versioning, hot load/unload
├── sdk/
│   ├── python/       # nova-agent-sdk
│   └── rust/          # nova-agent-sdk-rs (future)
├── execution-backends/
│   ├── inprocess/    # only one enabled in Phase 3
│   ├── subprocess/    # Phase 4+
│   ├── container/     # Phase 7+
│   └── remote/         # Phase 8
└── supervisors/       # built-in domain supervisor agents

agents/
├── research-agent/
├── architect-agent/
├── coding-agent/
├── qa-agent/
├── documentation-agent/
└── ...
```

Doc 02 (`:162-169`) is explicit that **neither directory is an instance of
the standard engine template**: `agent-os/kernel` is control-plane
infrastructure, not an always-on FastAPI service; `agents/<name>-agent`
follows the Agent Package format (doc 12 §3), a dynamically loadable unit,
not a service.

### 5.2 Concrete config changes needed

| File | Current state | Needed change |
|---|---|---|
| `pnpm-workspace.yaml` | `packages: ["apps/*", "packages/*", "services/*"]` | Add `"agent-os/*"` (for `agent-os/sdk/python`, if it ships a `package.json` for TS-side SDK pieces) — confirm exact need in TDD 3E. |
| `pyproject.toml` `[tool.uv.workspace] members` | `["packages/*", "services/*"]` | Add `"agent-os/*"` glob (for `agent-os/kernel`, `agent-os/sdk/python`, `agent-os/registry`, `agent-os/supervisors` as uv workspace members). |
| `pyproject.toml` `[tool.importlinter] root_packages` | 13 entries (11 engines + `nova_testkit` + `nova_service_kit`) | Add each new agent-os module's top-level package name as it's scaffolded. |
| `pyproject.toml` `nova_service_kit` ADR-034 contract `forbidden_modules` | 11 engine module names | Add `agent_os_kernel` (or equivalent) once `agent-os/kernel` exists and consumes `nova-service-kit` (§5.3 confirms it can). |
| `.github/workflows/build-and-scan.yml` `matrix.service` | 11 entries | Add `planning-engine`, `action-engine`, `capability-engine`; add `agent-os-kernel` if it ships as its own container image. |
| `.github/workflows/real-infra-checks.yml` `matrix.include` | 5 entries (real-Postgres only) | Add new engines only once they have real-Postgres repository tests — not automatic. |
| `.github/workflows/pr-checks.yml` | No per-package matrix | **No change needed** — automatically comprehensive via the pnpm/turbo workspace once new packages are registered above. |
| `infra/docker/docker-compose.local.yml` | 11 engine + 2 worker service blocks | Add `planning-engine`(+worker), `capability-engine`(+worker), `action-engine`(+worker); add `agent-os-kernel` if deployed as its own container. |

### 5.3 `tools/scaffold-engine.py` cannot be used as-is for `agent-os/kernel`

Confirmed via full-file read (`tools/scaffold-engine.py`, 452 lines):

1. `_NAME_PATTERN` (line 28) requires the name to end in `-engine` —
   `kernel`/`registry`/`agent-os/kernel` all fail immediately.
2. `SERVICES_DIR = REPO_ROOT / "services"` (line 25) is hardcoded — no
   parameter targets `agent-os/` or `agents/`.
3. The generated skeleton assumes an always-on FastAPI/uvicorn service
   (Dockerfile with `EXPOSE 8000`), which doc 02 explicitly says
   `agent-os/kernel` is not.
4. `_update_root_pyproject`'s contract-matching (keyed to exact
   `[[tool.importlinter.contracts]] name` strings) has no path for
   agent-os-style modules.

**Recommendation:** `agent-os/kernel`, `agent-os/registry`,
`agent-os/supervisors` need either a small, separate scaffold script (or a
`--target-dir`/`--no-fastapi` extension to the existing one) as part of
TDD 3E's own prerequisite work — this is a real, concrete, small piece of
tooling work, not a design fork.

### 5.4 `nova-service-kit` is reusable for `agent-os/kernel`'s persistence

Confirmed: none of `create_engine`/`create_session_factory`
(`db.py:18-23`), `make_health_router` (`health.py:25-36`), or
`dispatch_ready_events` (`outbox.py:33-111`) contain engine-domain-specific
logic — all are parameterized over bare DSNs / structural Protocols. This
satisfies ADR-034 and confirms `agent-os/kernel` can use the same
Postgres-backed persistence pattern every other engine uses for its own
Task-assignment/Agent-instance-health state (doc 12 does not specify a
persistence technology for the Kernel's own state — only Task Graph
persistence is explicitly named, and that lives in `planning-engine`, not
the Kernel). **Note:** `bind_event_bus`/`BoundEventBus` (the Event Bus
connection helper) lives in `nova-eventbus-sdk`, not `nova-service-kit` —
correcting an imprecise premise from this pass's own research prompt.

### 5.5 `AgentResult`/`AgentMessage` have no field-level definition anywhere yet

Confirmed via full-file read of doc 12: both types are referenced by name
throughout (§4, §8, §10) but never given a concrete field list — only
`AgentMessageType` (the enum: `ASSIGN`, `PAUSE`, `RESUME`,
`PEER_REVIEW_REQUEST`, `PEER_REVIEW_RESULT`, `CONFLICT_ESCALATION`,
`DELEGATION`, `HEALTH_PING`, doc12 `:350-358`) is fully specified. This is
a real, disclosed documentation gap — not a discrepancy, since doc 12 never
claims to have defined them — but a required TDD 3E deliverable: define
`AgentResult` and `AgentMessage` field-level shapes before any agent can be
built against them.

---

## 6. Prerequisites and blockers

1. **Phase 2D-D real-infra confirmation (§0)** — standing discipline,
   still open, blocks all Phase 3 implementation.
2. **`agent-os/kernel` scaffolding tooling gap (§5.3)** — small, concrete,
   must be resolved (script extension or manual scaffold) before TDD 3E's
   implementation can begin, though it does not block TDDs 3A-3D.
3. **Workspace/CI registration (§5.2)** — mechanical, but must happen
   before each new engine's first commit, per the existing per-engine
   convention.
4. **`AgentResult`/`AgentMessage` field-level definition (§5.5)** — must be
   decided during TDD 3E's own design work, before any agent package can
   implement `AgentHandler`.
5. **NEW, significant: `api-gateway` + `ws-gateway` + base `apps/web-client`
   shell do not exist** (§11) — Phase 3's roadmap line ("Planning + Agent
   Activity panels added") presupposes a base that was never built. This
   is a real, load-bearing prerequisite gap, not a minor detail — flagged
   prominently rather than folded silently into an existing TDD slice (see
   §7's explicit callout).
6. **Fork E2's mechanism (§2.2)** is design-ready but unbuilt — TDD 3D must
   finalize exact `action.approval.*` subject names and the pending-approval
   persistence shape before action-engine's approval loop can be
   implemented.

---

## 7. Proposed TDD split (3A-3E) — revised in light of this pass's findings

The original Fork-1 sketch bundled capability-engine and action-engine
into one TDD. Given both now carry substantial, independently-reviewable
security-relevant design surface (capability sandboxing depth, Fork E3;
the self-contained approval loop, Fork E2), and given Fork E5's approved
pull-forward of the reasoning-engine recursion trigger, the following
5-way split is proposed — still exactly 5 TDDs (3A-3E), matching the
user's approved count, but re-sequenced around dependency reality rather
than the roadmap's raw step order:

| TDD | Scope | Depends on |
|---|---|---|
| **3A** | reasoning-engine Multi-step recursion trigger only (Fork E5) | Nothing new — existing engine, existing fields. Lowest-risk, closes long-standing Phase 2B debt independently. |
| **3B** | `planning-engine`: Task Graph model, decomposition, Postgres persistence, `nova-contracts` `events/planning.py` additions (`planning.task_graph.created`, `planning.decompose.request`) | `reasoning-engine` (existing, `reasoning.result`), `communication-engine` (existing, for progress reporting). |
| **3C** | `capability-engine`: registry, lighter OS-level sandboxing (Fork E3), 4 foundational capabilities | Nothing new beyond existing infra. |
| **3D** | `action-engine`: Action Object Model, risk pipeline, terminal/filesystem/git adapters, rollback, self-contained approval loop (Fork E2) | `capability-engine` (3C) — agents/actions execute against capabilities. |
| **3E** | `agent-os/{kernel,sdk,registry,supervisors}` + 5 agent packages + `engineering` Supervisor + `GoalsPort` real-RPC migration (both engines) | `planning-engine` (3B, Task Graphs to consume), `capability-engine` (3C), `action-engine` (3D) — agents need all three to do real work. |

**Explicitly flagged, not silently folded in:** `apps/web-client`'s
Planning + Agent Activity panels, plus the `api-gateway`/`ws-gateway`
bring-up they depend on (§11), **do not fit cleanly into any of 3A-3E as
scoped above.** This is new information discovered during this pass, after
the user's approval of the 3A-3E split. Recommend surfacing this to the
user directly as a decision point before TDD writing begins (see the
closing section of this document) rather than silently assigning it to 3E
or silently dropping it from scope.

---

## 8. Verification strategy per TDD

Following the established two-tier convention (ADR-033) unchanged for all
five TDDs: fast/fake-backed default suite (`pytest -m "not real_infra"`,
85% domain-coverage gate via `--cov=<pkg>.domain`) plus
`@pytest.mark.real_infra` tests excluded from default runs, confirmed only
via GitHub Actions' nightly `schedule` trigger (manual `workflow_dispatch`
remains blocked per the standing 403 precedent).

| TDD | Locally verifiable | Requires real infrastructure |
|---|---|---|
| 3A | Full — pure pipeline logic, no new external dependency. Structural assertions on recursion depth/confidence-aggregation per doc 16 §5's "structural verification, not output-string matching" philosophy. | None new. |
| 3B | Domain logic (decomposition, dependency/critical-path analysis), fake-backed repository tests. Structural Task Graph assertions (no cycles, expected shape) per `ENGINEERING_ROADMAP.md:535`. | Real-Postgres persistence + restart-survival test (roadmap acceptance criterion `:545` — killing `agent-os-kernel` mid-execution and resuming — needs real Postgres, not fakes). |
| 3C | Registry logic, permission-scope-boundary unit tests. | Sandboxed execution test proving no capability escapes its declared scope (`ENGINEERING_ROADMAP.md:536`) needs a real (lightweight) sandboxed process, not a fake. |
| 3D | Risk-pipeline logic, approval-state-machine unit tests (fake `CommunicationPort`, mirroring digital-twin-engine's `FakeCommunicationPort` precedent). Rollback-strategy unit tests. | Real end-to-end approval round trip (real Postgres for the pending-approval record, real communication-engine call) — mirrors the Phase 2D-D Fork D real-wire-round-trip test pattern. |
| 3E | Agent SDK contract tests (every shipped agent validated against `AgentHandler` before registration, `ENGINEERING_ROADMAP.md:537`). Supervision-restart-strategy unit tests (force a crash, assert `one_for_one` behavior). | The full scripted integration test named in the roadmap (`:538`: "add a health-check endpoint to a sample repo" flowing Reasoning → Planning → NAOS → Action → a real git commit in a throwaway repo) is inherently a real-infra-class test — real git repo, real agent execution, real Postgres-backed Task Graph. |

---

## 9. Anything intentionally deferred to Phase 4 or later

Reconfirmed from the prior research pass, plus explicit reaffirmation per
user decision 9:

- **`autonomy-engine`** entirely — including the `autonomy.approval.requested`/
  `autonomy.decision.made` event subjects (deliberately left undefined in
  Phase 3, per Fork E2's resolution, so `autonomy-engine` can claim that
  namespace cleanly in Phase 4 without a Phase 3 collision).
- **`subprocess`/`container`/`remote` execution backends** (Phase 4+/7+/8).
- **Full gVisor/Firecracker capability sandboxing** (Phase 7+, per Fork E3).
- **Multi-level supervision trees** beyond the single `engineering`
  Supervisor (mechanism exists from Phase 3 per doc 12 §15, exercised
  later).
- **Git/HTTP/marketplace-style Agent Registry discovery** (Phase 8+;
  filesystem-only in Phase 3).
- **`nova-auth`'s full RBAC/OIDC implementation** (Phase 7,
  `ENGINEERING_ROADMAP.md:699`) — confirmed via `services/nova-core/.../boot.py:85`
  that `nova-auth` doesn't exist in any form yet; Phase 3's action-engine
  permission checks are necessarily self-contained/local until then.
- **Autonomy + Digital Twin panels** in `apps/web-client` (Phase 4,
  `ENGINEERING_ROADMAP.md:574`).
- **`GoalsPort`'s real-RPC migration is NOT deferred** — explicitly
  in-scope for TDD 3E (user decision 6), once `planning-engine` exists.

---

## 10. Updated recommended implementation order

Incorporating Fork E5's approved pull-forward and this pass's dependency
findings:

1. **TDD 3A** — reasoning-engine Multi-step recursion trigger (zero
   dependencies, can start as soon as Phase 2D-D closes).
2. **TDD 3B** — `planning-engine`.
3. **TDD 3C** — `capability-engine`.
4. **TDD 3D** — `action-engine` (depends on 3C).
5. **TDD 3E** — `agent-os/*` + 5 agents + `engineering` Supervisor +
   `GoalsPort` migration (depends on 3B, 3C, 3D).
6. **Explicitly flagged, sequencing TBD pending user decision (§7,
   §11):** `api-gateway` + `ws-gateway` bring-up, base `apps/web-client`
   shell, then Planning + Agent Activity panels.

This differs from the roadmap's raw 7-step order
(`ENGINEERING_ROADMAP.md:526-532`) in exactly two respects, both
user-approved: the recursion trigger moved from last to first (Fork E5),
and capability/action-engine given independent TDD slices rather than one
bundled TDD (a refinement of Fork E1's "Option A," not a contradiction of
it).

---

## 11. New finding requiring explicit attention: the `apps/web-client` / gateway gap

Called out separately here, not buried, because it changes both scope and
schedule materially and was discovered only during this pass.

**The facts, all confirmed directly:**

- `ENGINEERING_ROADMAP.md:450-452` lists `api-gateway` + `ws-gateway`
  "minimal implementation" **and** `apps/web-client`'s first panel
  ("the first real UI") as **Phase 2D** deliverables.
- `docs/design/phase-2d/00-master-blueprint.md:141-145` confirms both were
  in Phase 2D's own in-scope list, and neither appears in that same
  document's "§3.2 Explicitly NOT inside Phase 2D" exclusion list.
- **Neither was ever built.** `services/` contains no `api-gateway` or
  `ws-gateway`; `apps/` does not exist anywhere on disk (confirmed by
  `find . -iname apps -type d`, zero results).
- Every Gate Review from Phase 1 through Phase 2D-B carries an explicit
  "0 React files" line in its metrics table, each time noting
  "`apps/web-client` remains a later-phase deliverable" — an implicit,
  un-adjudicated re-deferral repeated phase over phase, never surfaced as
  an explicit scope decision requiring approval. `phase-2d-d-gate-review.md`
  (the most recent) doesn't mention it at all.
- Phase 3's roadmap deliverable line, *"`apps/web-client`: Planning + Agent
  Activity panels added"* (`ENGINEERING_ROADMAP.md:518`), uses the word
  "added" — grammatically presupposing a base shell that exists to add
  panels to. It doesn't exist.

**This is the mirror image of the reasoning-engine finding (§2.5): there,
the roadmap's prose implied more missing work than actually exists. Here,
the roadmap's prose implies less missing work than actually exists** —
"Planning + Agent Activity panels added" reads as a small increment; it is
actually "build `api-gateway`, build `ws-gateway`, build the base
`apps/web-client` shell (routing, panel-loading infra, realtime/ WebSocket
client, TanStack Query cache wiring, auth session hook), *then* add two
panels."

**Not silently resolved here.** This document does not decide whether
Phase 3 absorbs this additional scope, whether it becomes an explicit
prerequisite slice ahead of TDD 3B, or whether the user wants to
descope `apps/web-client` out of Phase 3 entirely (leaving Planning/Agent
Activity observable only via each engine's own direct `/v1/...` REST
surface, consistent with the Fork E2 stopgap precedent, until the gateway
layer is built later). This is squarely a scope decision for the user,
not one this research pass is authorized to make.

---

## Executive summary

**Phase 2D-D remains open** — unchanged from the last check, no new
real-infra run has fired against the fix commit.

**All 10 of the user's approved architectural decisions are confirmed
consistent with the evidence found this pass**, with two decisions
(E2 approval-loop mechanism, E4 frontend stack) turning out to have
sharper or more complete existing documentation than the prior research
pass surfaced — both resolved with citations above, neither requiring a
new decision beyond what was already approved.

**Forks E1, E3, E5, E6 are confirmed as approved with no new evidence
against them.** **Fork E2** is confirmed as approved, now with a concrete,
evidence-grounded mechanism proposal (new `action.approval.*` subjects,
stopgap direct-REST decision endpoint, reserving `autonomy.approval.*` for
Phase 4). **Fork E4 turns out not to be an open fork at all** — docs 01 §6
and 04 already fully specify the frontend stack; the earlier "no
recommendation" finding is corrected here.

**One significant, previously-undetected gap requires the user's explicit
attention before TDD writing begins:** `api-gateway`, `ws-gateway`, and the
base `apps/web-client` shell were nominally Phase 2D deliverables that
were never built, and Phase 3's own roadmap line for `apps/web-client`
presupposes they exist. This is flagged in §11 and is not resolved by
this document.

**Four discrepancies were investigated and documented, not corrected:**
doc 06's stale "Agent Orchestrator" wording (terminology only, no
substance conflict); the Phase 2B gate review's internal
self-contradiction about Multi-step's reachability; doc 20's silence on
Phase 3 (correctly silent — the real boundary document is
`phase-2c/00-executive-cognition-engine.md` §5.7-§5.10); and two new
findings — doc 13's Bible-citation error (attributes Part 14's risk-tier
scale to Part 12) and Bible Part 04's informal/formal agent-naming
inconsistency (neither requiring correction).

**No production code was written or modified during this pass.** TDD
writing is not authorized to begin until the user reviews this document,
resolves the `apps/web-client`/gateway scope question (§11), and confirms
Phase 2D-D's real-infra closure has landed.

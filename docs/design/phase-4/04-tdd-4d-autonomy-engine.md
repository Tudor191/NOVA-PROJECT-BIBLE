# TDD 4D — `services/autonomy-engine`, the Trust/Policy/Permission surface,
## and the `autonomy/` panel

**Milestone:** Phase 4 milestone **4D — Autonomy**
**Authoritative scope:** [`00-master-scope.md`](00-master-scope.md) §5 (4D), §6, §7, §15
**Satisfies:** **AC-5**
**Depends on:** 4C (merged; `phase-4` head `b1d7ca5`), D-3, D-6
**Status:** Design preparation. **Not implemented. `phase-4d` is not created.**

Written immediately before the milestone begins, per §17's stated cadence.

---

## 0. Objective

Build `services/autonomy-engine`: the engine that decides **whether an action
should occur**, distinct from the engines that decide what to do
(`reasoning-engine`), how to organize it (`planning-engine`), or how to carry it
out (`action-engine`). Bible Part 14's own architectural requirement states the
separation exactly:

> *"Reasoning produces options. Planning organizes work. Action executes
> operations. The Autonomy Engine decides whether execution should occur."*

4D delivers the smallest coherent slice of that engine which makes **AC-5**
demonstrable and gives **CF-9** the policy surface it was routed to:

- **Autonomy Levels 0–2 defined**; **Levels 0–1 enabled**; **Level 2 defined but
  not selectable** — D-1 assigns enabling Level 2 to **4F**.
- **No automatic execution at any level 4D enables.** At Levels 0–1 every
  proposal terminates at the user.
- **Trust Engine**, consuming 2D-D's existing conversational trust signal as one
  input rather than re-deriving an unrelated one.
- **Policy Engine** — user-authored rules that override autonomous decisions.
- **Permission Matrix** — Bible Part 14's ten permission categories, granularly
  configurable.
- **`autonomy/` panel** — level selector, trust score, policy editor, suggestion
  inbox.
- **CF-9 discharged**: a creation surface for the ADR-032 identity-confidence
  policy that `action-engine` already enforces and models but that nothing in the
  repository can create.

---

## 1. Scope

| # | Deliverable | Notes |
|---|---|---|
| 1 | `services/autonomy-engine` scaffolded via `tools/scaffold-engine.py` | Ordinary FastAPI service under `services/`, like every engine since 2A |
| 2 | Autonomy Level model, Levels 0–5 named, **0–2 defined**, **0–1 selectable** | Bible Part 14 "Autonomy Levels" verbatim vocabulary |
| 3 | Trust Engine — per-category trust scores, consuming 2D-D's `TrustMetric` | §5 |
| 4 | Policy Engine — user-authored policies that override decisions | §6 |
| 5 | Permission Matrix — ten categories × granular configuration | §7 |
| 6 | `autonomy.decision_log` persistence | Doc 07's canonical table, §9 |
| 7 | Suggestion lifecycle — proposed → approved/rejected/expired | §4.3; this is what AC-5 measures |
| 8 | Event contracts `autonomy.*` in `nova-contracts` + SDK subject registration | §8.2 |
| 9 | REST surface `/v1/autonomy/*` on the engine, fronted 1:1 by `api-gateway` | §8.1, D-6 |
| 10 | **CF-9 creation surface** for `IdentityConfidencePolicy` | §11 |
| 11 | `autonomy/` panel in `apps/web-client` | §12 |
| 12 | CI: `build-and-scan` matrix entry, `real-infra-checks` entry, import-linter contract, compose service, migration wiring | §15 |

### 1.1 What 4D deliberately does **not** build

Bible Part 14 describes a far larger engine than 4D builds. The following Part 14
sections are **named here as future work so their absence is disclosed rather
than silently narrowed**, per protocol principle 0.3.6:

Initiative Engine (opportunity *detection*), Proactive Assistance, Interruption
Awareness, Objective Monitoring, Self Scheduling, Adaptive Autonomy, Autonomy
Memory beyond the decision log, Multi-Agent Autonomy coordination, Governance
tiers beyond personal policies, Reversibility/rollback orchestration, the
Explanation Engine beyond the decision log's stored rationale, and Autonomy
Profiles.

**4D builds the decision surface, not the initiative surface.** A suggestion in
4D originates from an explicit request or an existing engine's event, never from
autonomous opportunity scanning — because scanning without Level 2+ execution
produces proposals nothing can act on, and Level 2 is 4F's.

---

## 2. Non-goals

Inherited from master scope §13 and restated because a reader of this document
alone must not infer otherwise:

- **Enabling Autonomy Level 2.** Defined here, enabled in **4F** (D-1). The
  level selector must refuse it.
- **Any automatic execution.** At Levels 0–1 nothing executes without an
  explicit user decision. There is no code path in 4D that calls
  `action-engine`'s execution surface on NOVA's own initiative.
- **Levels 3, 4, 5.** Named in the vocabulary for completeness; not defined,
  not modelled, not selectable.
- **The desktop shell** (Phase 5), **the five deferred panels** (Phase 5),
  **voice UI presentation** (Phase 5), **`@nova/ui` as a finished design
  system** (Phase 5).
- **Full OIDC / PKCE via a real `nova-auth`** — Phase 7. D-3's session model
  governs, unchanged.
- **Multi-user support or RBAC of any kind.** ADR-025's single-trusted-user
  model is preserved exactly; see §10.
- **Permission-derived subscription allow-lists.** Phase 4's allow-list stays a
  fixed, bounded list, not a policy engine — §10.
- **Any provider implementation.** 4D adds no model provider and does not
  resolve AC-4's deferred clauses; see §3.3.
- **Phase 5 work of any kind.**

---

## 3. Dependencies and inherited state

### 3.1 Hard dependencies

| Dependency | State | Why 4D needs it |
|---|---|---|
| 4C merged into `phase-4` | `b1d7ca5` | §7's implementation order; 4D branches from the merged head per §16 rule 5 |
| `api-gateway` route table (4A, D-6) | shipped | Forwards `/v1/autonomy` 1:1 |
| `ws-gateway` `PUBLIC_TOPICS` (4A/4B/4C) | shipped, 18 exact strings | §10 — any new browser-visible topic is an explicit addition, never a pattern |
| `apps/web-client` shell, `entities/`, `realtime/` | shipped | The panel is an additional route, not new infrastructure |
| `action-engine` risk + approval pipeline (3D) | shipped | 4D consumes its risk vocabulary and discharges CF-9 against its policy table |
| `digital-twin-engine` `TrustMetric` (2D-D) | shipped | §5 — the trust input 4D must consume rather than re-derive |

### 3.2 Authoritative decisions this TDD is bound by

| Decision | Effect on 4D |
|---|---|
| **D-1** (approved 2026-09-01) | Autonomy **Level 2 moves to 4F**. 4D defines it and must not enable it |
| **D-3** (approved) | Single long-lived local session validated by `api-gateway`; ADR-025 single-trusted-user. 4D introduces no second identity concept |
| **D-6** (approved) | `api-gateway` forwards 1:1, no path rewriting. 4D's paths are the shipped paths |
| **D-7** (approved) | The web app is the correct first UI; the panel is a web panel |
| **ADR-032** (all four points) | Identity confidence is a first-class authorization input; **point 2** is what CF-9 leaves unimplemented, and §11 discharges it |
| **ADR-025** | Single trusted user per instance |
| **ADR-006** ([`00-overview-and-decisions.md`](../../architecture/00-overview-and-decisions.md) §ADR-006 — it predates the `adr/` directory, which starts at ADR-011) **/ doc 09 §6** | `ws-gateway` is the sole realtime bridge; browser never reaches NATS |
| **ADR-033** | Two-tier testing; `real_infra` marker; 85% domain coverage |

**D-2, D-4, D-5 and D-8 are 4A/4B/4C decisions and are not 4D decisions.** They
are listed in master scope §11 and are unaffected by this milestone. This
document neither reinterprets nor extends them.

### 3.3 AC-4's deferral is untouched

AC-4 clause 1 is Met by 4C.1; clauses 2 and 3 remain **Deferred by explicit user
approval of 2026-09-07**, with provider configuration the only remaining trigger
(master scope §1.1). **The authoritative Phase 4 plan does not assign those
clauses to 4D**, and this TDD does not resolve, reinterpret or narrow them. 4D
adds no model provider.

Likewise: Phase 4C is exactly 4C.1 and 4C.2, both complete and merged. **This
document creates no 4C.3 and no other 4C milestone**, and introduces no new
Phase 4 milestone — the milestone set remains 4A–4F as master scope §5 defines
it.

---

## 4. Architecture

### 4.1 Position in the engine graph

Doc 10's engine graph already places `autonomy-engine` between
`executive-cognition-engine` and the executing engines, consulted by
`knowledge-engine`, and registered with `nova-core`. 4D implements that position,
it does not redraw it.

```
action-engine ──autonomy.approval.requested──▶ autonomy-engine
                                                    │
                            Level ▸ Policy ▸ Permission ▸ Trust ▸ Confidence
                                                    │
        ◀──autonomy.decision.made──────────────────┘
                                                    │
                                       autonomy.decision_log (append)
                                                    │
             api-gateway ──/v1/autonomy/*──▶ (REST reads + user decisions)
                                                    │
                                        ws-gateway ──▶ browser panel
```

### 4.2 The decision pipeline

Bible Part 14's Autonomy Principle lists eleven steps. 4D implements the
**gating subset** that Levels 0–1 can honour, in this fixed order, and names the
rest as deferred (§1.1):

| # | Step | 4D |
|---|---|---|
| 1 | Observe | **Deferred** — 4D receives events, it does not scan |
| 2 | Detect Opportunity | **Deferred** (Initiative Engine, §1.1) |
| 3 | Evaluate Importance | **Partial** — carried as the suggestion's own priority field, not scored |
| 4 | Estimate Risk | **Consumed, not re-derived** — `RiskLevel` arrives on the request |
| 5 | Check Policies | **Built** — §6 |
| 6 | Check Permissions | **Built** — §7 |
| 7 | Predict Outcome | **Deferred** |
| 8 | Decide | **Built** — §4.3 |
| 9 | Execute **or Request Approval** | **Request Approval only.** Levels 0–1 have no execute branch |
| 10 | Verify | **Deferred** (no execution to verify) |
| 11 | Learn | **Deferred** (Adaptive Autonomy, §1.1) |

**Order is binding and must be asserted by test.** A policy denial must be
reachable without consulting trust, and a permission denial without consulting
identity confidence — so that a deny is attributable to exactly one gate.

### 4.3 Decision outcomes

A decision is one of exactly four outcomes, and **`execute` is unreachable at
Levels 0–1**:

| Outcome | Meaning | Reachable at L0 | L1 | L2 (defined, not enabled) |
|---|---|---|---|---|
| `observe_only` | The level forbids proposing | ✅ | — | — |
| `propose` | A suggestion is recorded for the user | — | ✅ | ✅ |
| `deny` | A gate refused; the reason names which | ✅ | ✅ | ✅ |
| `execute` | Proceed without asking | **unreachable** | **unreachable** | defined; **disabled in 4D** |

A **negative control is required**: forcing `execute` at Level 1 must fail the
suite (§16).

---

## 5. Trust Engine — inputs and outputs

### 5.1 The 2D-D input, consumed not re-derived

Master scope §5 is explicit: *"The Trust Engine consumes Phase 2D-D's
conversational trust-development signal as one input rather than re-deriving an
unrelated one."* The 2D-D blueprint states the axis distinction that makes this
a *consumption* rather than a merge:

> *"2D-D's trust-development tracking is a **conversational** trust signal (does
> the user rely on NOVA's judgment, correct it less often, etc.) — a distinct
> axis from Autonomy's **execution** trust (how much unattended action is
> permitted), and Phase 4's Trust Engine design must consume 2D-D's signal as
> one input rather than re-derive an unrelated one."*

The shipped signal is `digital_twin_engine.domain.models.TrustMetric`:

```python
class TrustMetric(BaseModel):
    user_id: UUID
    correction_frequency: float | None = None      # None = no data yet, NOT zero
    window_session_count: int = 0
    clarification_acceptance_rate: float | None = None         # reserved, never computed in 2D-D
    proactive_suggestion_acceptance_rate: float | None = None  # reserved, never computed in 2D-D
    computed_at: datetime
```

**Three properties of that contract are load-bearing and must not be flattened:**

1. `correction_frequency` is `float | None`, and `None` means *"no completed
   sessions in the window"* — 2D-D's own docstring says *"'no data yet' is not
   the same claim as 'measured zero corrections'"*. 4D **must not coerce `None`
   to `0.0`**, which would read as perfect trust.
2. The two `*_acceptance_rate` fields are **reserved and always `None`** in 2D-D
   — deferred, not fabricated. 4D reads them if present and must not compute
   them; computing them here would re-derive 2D-D's own deferred work in the
   wrong engine.
3. It is a **conversational** signal. It is **one input**, never the trust score
   itself.

### 5.2 Trust Engine outputs

Per Bible Part 14 *"NOVA maintains a dynamic trust score for every category"*,
scored **per permission category** (§7), not one global number:

```
TrustScore
  user_id: UUID
  category: PermissionCategory          # §7's ten categories
  score: float | None                   # None = insufficient evidence, never 0.0-by-default
  evidence_count: int
  inputs: {conversational: TrustMetricSnapshot | None,
           execution: ExecutionOutcomeSummary | None}
  computed_at: datetime
```

- **`score is None` is a first-class state, and it is fail-closed**: an unknown
  trust score never satisfies a threshold. This mirrors `action-engine`'s own
  absent-policy idiom and 2D-D's `None` discipline.
- The `execution` input is **empty in 4D by construction** — nothing executes at
  Levels 0–1, so there are no execution outcomes to learn from. The field exists
  now and stays `None`, following 2D-D's own precedent of declaring a reserved
  field rather than migrating it in later.
- **Trust never raises an autonomy level by itself.** Bible Part 14: *"As NOVA
  demonstrates reliable performance, **the user may** gradually increase
  autonomy."* Level changes are a user action (§12), never a computed one.

### 5.3 Cross-engine read

`digital-twin-engine` owns `TrustMetric`; `autonomy-engine` must not read its
tables. The read is an **Event Bus request/reply**, matching the boundary
discipline doc 20 enforces and import-linter asserts. If the reply times out or
the metric is absent, the conversational input is `None` and the resulting trust
score is `None` — fail-closed, never a default number.

---

## 6. Policy Engine — inputs and outputs

Bible Part 14: *"Policies override autonomous decisions… Policies remain
absolute unless modified by the user."*

```
Policy
  id: UUID
  user_id: UUID
  name: str
  effect: "deny" | "require_approval"   # 4D has no "allow" effect — see below
  match: PolicyMatch                    # category, risk floor, capability class, time window
  enabled: bool
  created_at / updated_at
```

**There is deliberately no `allow` effect in 4D.** An `allow` policy can only
matter where something would otherwise not happen automatically — i.e. at Level
2+, which 4D does not enable. Adding it now would ship an effect with no
reachable behaviour and invite a later reader to assume auto-execution exists.

**Evaluation semantics, binding:**

1. Policies are evaluated **before** permissions and trust (§4.2).
2. **Deny wins.** Any matching `deny` ends the pipeline; no later gate can
   overturn it. This is Part 14's *"Governance always overrides"* at the
   personal-policy tier.
3. `require_approval` is **already the Level 0–1 behaviour**, so at those levels
   it is a no-op that is still *recorded* in `policy_checks` — the decision log
   must show which policies were consulted, not only which fired.
4. **An empty policy set is not permissive.** It means no policy overrode the
   level's own behaviour, and the level's own behaviour at 0–1 is never
   execution.

---

## 7. Permission Matrix

Bible Part 14's ten categories, verbatim and in order:

`read` · `analyze` · `recommend` · `create` · `modify` · `delete` · `execute` ·
`deploy` · `purchase` · `communicate`

```
PermissionGrant
  user_id: UUID
  category: PermissionCategory
  max_risk: RiskLevel | None            # None = no autonomous authority in this category
  requires_approval_above: RiskLevel | None
  updated_at: datetime
```

- **`RiskLevel` is reused verbatim, never redefined.** The canonical scale is
  `nova_contracts.events.planning.RiskLevel` — `negligible`, `low`, `moderate`,
  `high`, `critical` — whose own docstring records it as *"the one canonical
  risk-tier scale anywhere in this project"*, taken from Bible Part 14 lines
  271–279. 4D introduces no second scale and no mapping layer.
- **Absent grant fails closed**: no row means no autonomous authority, not
  unlimited authority. Same idiom as `IdentityConfidencePolicy` and
  `ProactiveBoundaryPolicy`.
- *"Each permission should support granular configuration"* is satisfied by
  per-category rows with their own risk ceilings, not by one global setting.

---

## 8. Contracts

### 8.1 REST — `/v1/autonomy/*`

Master scope §8 records the boundary question and assigns it here: *"`/v1/autonomy/...`
is a real future surface owned by `autonomy-engine` (4D), distinct from
`action-engine`'s existing approval endpoint. Both will exist; they are not
duplicates. **4D defines the boundary.**"*

**The boundary, defined:**

> `action-engine`'s `POST /v1/action/approvals/{id}/decide` decides **one
> already-created `Action`** inside its own execution pipeline. `autonomy-engine`'s
> `/v1/autonomy/*` governs **whether NOVA may act at all** — levels, policies,
> permissions, trust, and the suggestions those produce. An autonomy suggestion
> that a user approves may *result in* an Action, which `action-engine` then
> decides and executes under its own pipeline. **Neither endpoint is reachable
> from the other's domain, and neither is deprecated by this milestone.**

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/autonomy` | Overview: current level, per-category trust, counts. One call for the panel's first paint, matching 4C's `/v1/agents` shape |
| `GET` | `/v1/autonomy/suggestions` | Suggestion inbox; keyset paginated on an opaque cursor, **no offset** |
| `POST` | `/v1/autonomy/suggestions/{id}/decide` | `{"decision": "approve" \| "reject"}` — the AC-5 control |
| `GET`/`PUT` | `/v1/autonomy/level` | Read/set the level. **`PUT` rejects 2–5 with 422** |
| `GET`/`POST`/`PATCH`/`DELETE` | `/v1/autonomy/policies[/{id}]` | Policy editor |
| `GET`/`PUT` | `/v1/autonomy/permissions` | Permission Matrix |
| `GET`/`PUT` | `/v1/autonomy/identity-confidence-policy` | **CF-9**, §11 |

`api-gateway` gains **one** `UpstreamRoute` entry, prefix `/v1/autonomy` →
`autonomy-engine`, forwarded 1:1 (D-6). Prefix matching covers the subtree, as
it does for `/v1/agents`.

### 8.2 Events

Doc 10 already names the canonical subjects; 4D implements them and registers
them in `nova-eventbus-sdk` (**none exist there today** — verified).

| Subject | Direction | Doc 10 row |
|---|---|---|
| `autonomy.approval.requested` | `action-engine` → `autonomy-engine` | 8 |
| `autonomy.decision.made` | `autonomy-engine` → requester / `communication-engine` | 8 |
| `autonomy.opportunity.detected` | `autonomy-engine` → `executive-cognition-engine` | 13 |

**`autonomy.opportunity.detected` is declared in the contract package and
registered, but 4D publishes it from no code path** — opportunity detection is
the deferred Initiative Engine (§1.1). Declaring the payload now and leaving it
unpublished is the honest shape; **it must not be added to `PUBLIC_TOPICS`**,
because a public topic nothing publishes is one a browser subscribes to and then
waits on forever — the exact mistake 4C's decision D-4 declined to repeat with
the `agent.*` family (master scope §6's corrected `agents/` row).

New payloads go in `packages/nova-contracts/src/nova_contracts/events/autonomy.py`
with contract tests, and the TypeScript is regenerated in the same commit (§8
of the protocol).

---

## 9. Persistence

Doc 07 already specifies the canonical table; 4D implements it as written:

```sql
CREATE TABLE autonomy.decision_log (
    id UUID PRIMARY KEY,
    action_id UUID NOT NULL,
    autonomy_level SMALLINT NOT NULL,
    risk TEXT NOT NULL,
    confidence REAL NOT NULL,
    policy_checks JSONB NOT NULL,
    outcome TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Plus the four tables the surfaces above require: `autonomy.autonomy_level` (one
row per user), `autonomy.policy`, `autonomy.permission_grant`,
`autonomy.suggestion`.

**Binding persistence rules:**

- **`decision_log` is append-only.** No `UPDATE`, no `DELETE` — Bible Part 14's
  *"Store every important autonomous decision"* and 4C.2b's `agent_activity`
  precedent. Asserted by a test that inspects the repository for the absence of
  those methods, as `agent-os/kernel` does.
- **One logical operation, one transaction, one commit** — decision D-3's
  transactional discipline as 4C.2 applied it. A suggestion's status change and
  its decision-log row are written in the **same transaction**.
- **A `relationship()` or an explicit `flush()` is required** wherever a child
  row carries a foreign key to a row created in the same unit of work. 4C.2's
  `4eafa80` defect — SQLAlchemy ordering unrelated mappers by name and emitting
  the child INSERT first — is a known trap in this codebase and must be
  designed out rather than rediscovered.
- Keyset pagination on `(created_at DESC, id DESC)`; **no offset anywhere**.

---

## 10. Security boundaries

**Nothing in 4D weakens an existing control. Each of these is asserted by test,
not by inspection.**

1. **The browser never reaches NATS.** ADR-006 / doc 09 §6 unchanged;
   `ws-gateway` remains the sole realtime bridge.
2. **`PUBLIC_TOPICS` grows by exact strings only.** If the panel needs realtime,
   it gets **at most `autonomy.decision.made`**, added as an exact string.
   `autonomy.*` must never be added — `BoundEventBus` matches with `fnmatchcase`
   where `*` spans dots, so the wide form would subscribe the gateway process to
   every future `autonomy.*` RPC subject. This is 4C.2e's finding, and it applies
   here unchanged.
3. **`autonomy.approval.requested` is internal.** It carries the engine's
   authorization inputs and must be rejected from browser subscription.
4. **`/internal/*` remains unroutable**; `api-gateway`'s route table is an
   allow-list of exact prefixes, not a pattern (D-6).
5. **Single-trusted-user preserved.** ADR-025 and D-3 unchanged. Every table is
   keyed by `user_id` because the schema already is, **not** because 4D
   introduces multi-user: `Settings.primary_user_id` remains the only identity,
   and no RBAC concept, role, group or permission-derived allow-list is
   introduced. §13's non-goal is binding.
6. **No autonomy setting may weaken `action-engine`'s gate.** The Permission
   Matrix and Policy Engine can only ever *narrow* what is permitted relative to
   `action-engine`'s own pipeline. A 4D surface that lets a user grant more than
   `action-engine` allows would be a privilege-escalation path, and a negative
   control must prove it does not exist.
7. **CF-9's fail-closed default is preserved** — see §11.

---

## 11. CF-9 — explicit handling

**The carry-forward, verbatim from master scope §4:** ADR-032 decision point 2
requires every gating engine to expose *"a configurable identity-confidence
threshold per privileged capability (or per capability class), never a single
hardcoded system-wide threshold"*. `action-engine` **enforces** the gate
(`domain/pipeline.py:180-192`) and **models** the policy
(`domain/models.py:46`, table `action.identity_confidence_policy`), but
**nothing in the repository can create a policy row** — no endpoint, no seed, no
migration insert, no admin surface. Deferred by explicit user approval
2026-09-06 and **routed to 4D as the appropriate future policy surface**.

**What 4D builds — and, precisely, what it does not:**

| | |
|---|---|
| **Builds** | `GET`/`PUT /v1/autonomy/identity-confidence-policy`, and the panel control behind it, letting the user set `minimum_confidence_by_risk` per `RiskLevel` tier |
| **Builds** | Write-through to `action-engine`'s existing `action.identity_confidence_policy` **via `action-engine`'s own API or an Event Bus command — never by writing another engine's table**. Doc 20's ownership boundary and import-linter's contracts both forbid the direct write |
| **Does not build** | A new threshold model. `IdentityConfidencePolicy.minimum_confidence_by_risk: dict[str, float]` already exists and is reused unchanged |
| **Does not change** | The **fail-closed default**. Absent policy still means threshold `1.0`; absent identity signal still means confidence `0.0`. 4D adds the ability to *author* a policy, never a default that authors one implicitly |
| **Does not choose** | A threshold value. No seed, no suggested default, no zero-confidence policy. The user picks, or there is no policy — the same discipline Phase 4B applied when it declined to seed one to make its E2E green |

**Ownership is not reassigned.** CF-9's originating owner remains Phase 3D /
ADR-032; 4D is the routed *surface*, as recorded. Closing CF-9 is a 4D
deliverable; re-opening AC-3 is not, and 4D makes no claim about AC-3.

---

## 12. Frontend — the `autonomy/` panel

Master scope §6 assigns `autonomy/` to 4D; §5 names its four widgets. Built on
the shell, `entities/` and `realtime/` that 4A shipped, following 4C.2f's
conventions exactly.

| Widget | Behaviour |
|---|---|
| **Level selector** | Shows Levels 0–2 with Bible Part 14's names — Observation Only, Suggestive, Assisted. **0 and 1 selectable; 2 visibly present and disabled**, labelled as enabled in a later milestone. Levels 3–5 are not rendered |
| **Trust score** | Per-category. **`None` renders as "insufficient evidence", never as 0** — the 2D-D discipline carried into the UI |
| **Policy editor** | List, create, edit, enable/disable, delete. `deny` and `require_approval` only |
| **Suggestion inbox** | The AC-5 surface: each suggestion shows what is proposed, its risk, which gates passed, and **Approve / Reject**. Nothing executes on render |

**Binding frontend rules, inherited from 4A/4B/4C and re-asserted:**

- **No polling** — no `refetchInterval`, no `setInterval`.
- **No optimistic mutation of shared cognitive state.** A decision POSTs, then
  invalidates; the server's response is the truth. 4C.2f's refetch-not-patch
  reasoning applies identically.
- **No fabricated data.** An empty inbox is a healthy empty state naming why,
  exactly as 4C.2f's provider-free state does — never seeded suggestions.
- **Strict schemas** mirroring the engine's response models; unknown fields fail
  the parse rather than being silently dropped.
- A **mutation** exists here for the first time in a Phase 4 panel
  (`POST …/decide`, `PUT …/level`). It is an explicit user action with a server
  round-trip, which is categorically different from the optimistic cache writes
  the no-optimistic-mutation rule forbids. The distinction must be stated in the
  panel's own module docstring so a later reader does not "fix" it.

---

## 13. Failure and degraded behaviour

| Condition | Behaviour |
|---|---|
| `digital-twin-engine` unreachable | Conversational input `None` → trust score `None` → **fail-closed**. Panel shows "insufficient evidence", never a number |
| `action-engine` unreachable when writing the CF-9 policy | **503**, never a silent success. D-1's Registry precedent from 4C.2: a degraded upstream is never reported as a healthy empty result |
| Policy evaluation raises | **Deny**, logged, with the decision log recording the failure. A policy engine that fails open is not a policy engine |
| Identity confidence absent | `0.0`, as `action-engine` already does. Unchanged |
| Suggestion decided twice | Second decision is a **409**; the first stands. The decision log is append-only and records both attempts |
| Level set to 2–5 | **422** with the reason. Not silently clamped |
| Unknown suggestion id | **404**, distinguished from a valid suggestion with no gates recorded |

---

## 14. Observability

`configure_observability("autonomy-engine", …)` as every engine does;
`/internal/health`, `/internal/readiness`, `/internal/metrics` mounted by the
scaffold. Every **deny** logs which gate denied and why — Part 14's Explanation
Engine reduced to the one thing 4D can honestly provide: *what policies were
applied, what risks were considered*. Prometheus still scrapes only `nova-core`
(a carried-forward finding, 4C.2 Gate Review §13.3); 4D does not close it and
does not claim to.

---

## 15. CI requirements

Master scope §15 already assigns these; 4D executes them.

| Target | Addition |
|---|---|
| `build-and-scan.yml` | Matrix entry `autonomy-engine` (§15 assigns this to 4D) |
| `real-infra-checks.yml` | Matrix entry `autonomy-engine` — its repository has real SQL, so it needs the tier that found 4C.2's two defects |
| `pyproject.toml` | `nova_autonomy_engine` in `[tool.importlinter]` `root_packages` **and** in the "Engines are independent" contract's `modules` list |
| `[tool.uv.workspace]` | New member |
| `infra/docker/docker-compose.local.yml` | Service + `run-migrations.sh` wiring |
| `tools/tests/test_build_and_scan_matrix.py` | Picks up the new entry automatically; must stay green |

---

## 16. Test strategy

Two tiers per ADR-033, and the negative-control and flakiness discipline of
protocol §9.2.

**Default tier (no Docker):** domain unit tests for level semantics, policy
evaluation order, permission resolution, trust computation including every
`None` path; integration tests booting the real FastAPI app with the in-memory
fake repository; `vitest` panel tests.

**`real_infra` tier:** a `test_repository_real_postgres.py` exercising the real
Alembic chain, the append-only guarantee, keyset pagination across a tie, and
**the transaction coupling of a suggestion decision with its decision-log row**.
4C.2 is the reason this is mandatory rather than optional: source inspection and
a fake repository cannot exercise a foreign key, and that is exactly how the
`4eafa80` defect reached CI.

**Required negative controls — each must fail the suite when the property is
removed:**

1. Forcing `execute` at Level 1 → must fail.
2. Making Level 2 selectable → must fail.
3. Coercing `TrustMetric.correction_frequency` `None` → `0.0` → must fail.
4. Making an absent trust score satisfy a threshold → must fail.
5. Making an absent `PermissionGrant` permissive → must fail.
6. Letting a later gate overturn a policy `deny` → must fail.
7. Adding `autonomy.*` (or any wildcard) to `PUBLIC_TOPICS` → must fail.
8. Adding `autonomy.approval.requested` to `PUBLIC_TOPICS` → must fail.
9. Seeding a default `IdentityConfidencePolicy` → must fail.
10. Changing the absent-policy threshold from `1.0` → must fail.
11. A 4D surface granting more than `action-engine` permits → must fail.
12. Reporting a degraded upstream as an empty success → must fail.

**Coverage:** 85% on `nova_autonomy_engine.domain`, the centralized gate.
**Flakiness:** ≥10× for anything timing- or I/O-sensitive.

---

## 17. Acceptance criteria for 4D

| # | Criterion | Verified by |
|---|---|---|
| 1 | Levels 0–2 defined with Part 14's vocabulary; 0–1 selectable; 2 disabled | Unit + panel test; negative control 2 |
| 2 | No execution path exists at Levels 0–1 | Negative control 1 |
| 3 | Trust Engine consumes 2D-D's `TrustMetric`; does not re-derive it; `None` stays `None` | Unit test; negative controls 3, 4 |
| 4 | Policy Engine: deny wins, evaluated before permissions and trust | Unit test; negative control 6 |
| 5 | Permission Matrix: ten categories, absent grant fails closed | Unit test; negative control 5 |
| 6 | `autonomy.decision_log` append-only, matching doc 07 | Repository-absence test + `real_infra` |
| 7 | One transaction per logical operation | `real_infra` test |
| 8 | `/v1/autonomy/*` fronted 1:1 by `api-gateway` | Gateway routing test |
| 9 | Security boundaries preserved; no wildcard in `PUBLIC_TOPICS` | Negative controls 7, 8, 11 |
| 10 | **CF-9 discharged** — a policy can be authored; defaults unchanged | Integration test; negative controls 9, 10 |
| 11 | Panel renders all four widgets; no polling; no fabricated data | `vitest` |
| 12 | Degraded upstream → 503, never an empty success | Negative control 12 |
| **AC-5** | See §18 | §18 |

## 18. Explicit mapping to AC-5

> **AC-5** — *"An autonomous suggestion at Autonomy Level 1 is **proposed, not
> executed**, is visible in the Autonomy panel, and executing it requires
> explicit user approval."*

| Clause | Discharged by | Proof |
|---|---|---|
| *"An autonomous suggestion at Autonomy Level 1"* | §4.3's `propose` outcome, reachable only at Level 1+ | Unit test asserting L0 yields `observe_only` and L1 yields `propose` |
| *"is proposed, not executed"* | §4.2 step 9 has **no execute branch** at Levels 0–1 | **Negative control 1** — forcing `execute` at L1 must fail the suite |
| *"is visible in the Autonomy panel"* | §12's suggestion inbox | `vitest` test rendering a real suggestion from a real response shape |
| *"executing it requires explicit user approval"* | `POST /v1/autonomy/suggestions/{id}/decide` is the only transition out of `proposed`; the panel's Approve control is the only caller | Integration test: no other route or handler moves a suggestion out of `proposed`; 409 on double-decide |

**AC-5 is fully dischargeable within 4D and is not provider-dependent.** It
requires no model provider, no Level 2, and nothing from AC-4's deferred
clauses — the suggestion's *content* may be trivial; what AC-5 measures is that
it is proposed, visible, and gated on an explicit human decision.

**An end-to-end Playwright spec is required** and must assert the full chain in
the browser against the real stack, not merely the API: a suggestion appears,
nothing executes, approval is explicit.

---

## 19. Migration and rollout

- **Branch:** `phase-4d`, cut from the **freshly merged `phase-4` HEAD** per
  master scope §16 rule 5 — not from an older snapshot. **Not created by this
  TDD.**
- **One PR targeting `phase-4`**, never `main` (§16 rule 3). `main` stays at
  `7e273e6` for the duration of Phase 4.
- **Additive migrations only.** 4D creates a new `autonomy` schema and touches
  no existing engine's tables. The CF-9 write-through goes through
  `action-engine`'s own surface (§11), so `action.identity_confidence_policy` is
  unmodified in structure.
- **Reversible by construction:** with no policy authored and no level set, the
  system behaves exactly as it does today — absent policy fails closed, absent
  grant fails closed, absent trust fails closed. **Installing 4D changes no
  existing behaviour until a user configures something.**
- **Slice the milestone** as 4C.2 did, each slice separately reviewable and
  independently committed, with no slice able to fake the one before it. Every
  slice inherits protocol §0.2's deferred-obligations ledger.

---

## 20. Carried-forward items 4D inherits but does not close

| Item | Disposition in 4D |
|---|---|
| **AC-4 clauses 2 and 3** | **Untouched.** Deferred by user approval 2026-09-07; provider configuration is the only trigger; not assigned to 4D |
| **4C.1 has no Gate Review** | Phase 4 closure obligation; not 4D's |
| **Phase 4A has no Gate Review or health record** | Phase 4 closure obligation; not 4D's |
| `README.md` has no Phase 4 status line | Phase 4 closure obligation |
| Over-broad `communication.*` / `personality.*` bus patterns | Carried forward unchanged; 4D adds no wildcard and does not widen them |
| Prometheus scrapes only `nova-core` | Carried forward; §14 |
| CF-8's six Phase 3E narrowings | Unchanged |
| SLOC methodology Option A / Option B | Open, undecided |

**The Phase 4 milestone set is unchanged: 4A–4F.** This TDD creates no new
milestone, moves no Phase 5 scope into 4D, and alters no approved decision.
Writing it is **not** authorization to begin implementation.

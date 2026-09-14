# TDD 4E — `services/digital-twin-engine` extension, Bible Part 16's nine
## remaining domains, and the `digital-twin/` panel

**Milestone:** Phase 4 milestone **4E — Digital Twin**
**Authoritative scope:** [`00-master-scope.md`](00-master-scope.md) §5 (4E), §6, §7, §15
**Satisfies:** **AC-6**
**Depends on:** 4D (merged; `phase-4` head `76a9662`), D-3, D-6
**Status:** Design preparation. **Not implemented. `phase-4e` is not created.**

Written immediately before the milestone begins, per §17's stated cadence.

---

## 0. Objective

Extend `services/digital-twin-engine` from the single behavioural profile Phase
2D-D shipped into Bible Part 16's full domain model, **populated from real
Perception and Memory data rather than from anything this milestone invents**,
and surface it through the `digital-twin/` panel.

Part 16 states the engine's purpose directly:

> *"The Digital Twin Engine is responsible for building a continuously evolving
> model of the user's digital world."* … *"Never create assumptions without
> evidence."*

That second sentence is the binding constraint on this milestone. Every domain
4E adds must be derived from evidence that already exists in the repository, or
be explicitly reported as underivable. **No domain is populated from fabricated,
seeded or simulated data.**

---

## 0.1 Findings from deriving this TDD against the repository

Four discrepancies were found while deriving this TDD from the repository. Each
was reported rather than decided unilaterally, per protocol §13.3's stop rule.

> **Status after the 2026-09-14 ratification.** **0.1.1 and 0.1.2 are RESOLVED** —
> the user approved correcting master scope §5's enumeration and wording, and
> that correction is applied. **0.1.4 is disclosure only** and needs no decision.
> **0.1.3 remains OPEN**: the ratification covered §19's five questions and §5's
> enumeration, and did not reach AC-6's simulated-gap mechanism. The proposed
> resolution below stands as a proposal, and **§14.4's E2E design depends on it**.
> Each subsection's original "Proposed resolution" wording is left as written.

### 0.1.1 The master scope's domain parenthetical lists eight, not nine

Master scope §5's 4E paragraph reads:

> *"the remaining nine of Bible Part 16's eleven domains (goal model, project
> model, software/hardware environment, skill model, knowledge profile,
> productivity patterns, learning progress)"*

**The count "nine" is correct. The parenthetical is incomplete.** Expanding
"software/hardware environment" into the two domains Part 16 names separately,
the list enumerates **eight**: Goals, Projects, Software Environment, Hardware
Environment, Skill Profile, Knowledge Profile, Productivity Patterns, Learning
Progress.

**The ninth is `Personal Workflow`**, which Part 16 lists first and the
parenthetical omits. §4 below derives the full nine from Part 16 and from the
engine's shipped state, and the arithmetic closes exactly: 11 − 2 = 9.

**Proposed resolution:** treat Part 16's own list as authoritative, add
`Personal Workflow` to 4E's scope, and record an additive correction in master
scope §5. **No domain is invented by this** — `Personal Workflow` is Part 16's
own first domain.

### 0.1.2 "Nine remaining" requires counting `Preferences` as already shipped

Master scope §5 says the nine are "additive to the **Communication Profile**
domain shipped in Phase 2D-D", which implies 11 − 1 = 10 remaining, not nine.

The repository resolves it: **two** Part 16 domains ship today, not one —
`Communication Style` (as `CommunicationProfile`) and `Preferences` (as
`PreferenceEvolutionHistory`, the served RPC `digital_twin.preferences.get.request`,
and `GET /preferences`). With both counted, 11 − 2 = **9**, matching §5's own
number.

**Proposed resolution:** record in master scope §5 that `Preferences` is the
second already-shipped domain. **This closes no carry-forward and changes no
code.**

### 0.1.3 AC-6's "multi-week gap" has no defined simulation mechanism

AC-6 requires the project model to reconstruct *"what was I doing on Project X"*
**after a simulated multi-week gap**. Nothing in the repository defines what
"simulated" means here — there is no clock-injection facility, no time-travel
fixture, and no documented convention for simulated elapsed time.

**Proposed resolution:** simulate the gap **in the data, not in the clock** — seed
the E2E stack's `memory` rows with real `created_at` timestamps weeks in the past
through the **real** `POST /v1/memories` route, then assert the reconstruction.
This uses a real production write path and real persisted rows; it fabricates no
runtime behaviour and injects no fake clock. **This needs explicit ratification**,
because it is the one place where 4E's acceptance test authors its own input.
See §14.4.

### 0.1.4 Perception has no autonomous producer until 4F

`perception-engine` publishes seven real subjects with real consumers
(`world-model-engine` and `memory-engine` both subscribe). But the only way an
observation enters the system today is `POST /v1/perception/observations`.
**`nova-companion` — the Rust per-platform sensor source — does not exist**;
there is no `companion/` directory, and the roadmap assigns it to **4F**.

This is the same shape as **CF-11**: a correct, reachable surface with no
autonomous upstream trigger. It is **disclosed here, not designed around**. §5.1
states exactly which 4E domains are affected and what each does when its evidence
is absent.

---

## 1. Scope

| # | Deliverable | Notes |
|---|---|---|
| 1 | Nine Part 16 domains modelled in `digital-twin-engine`, **additive** to the two already shipped | §4 |
| 2 | Evidence ingestion from **real** Memory and Perception sources | §5 |
| 3 | `/v1/digital-twin/*` REST surface on the engine, fronted 1:1 by `api-gateway` | §7, D-6 |
| 4 | Persistence for the nine domains + their evidence provenance | §9 |
| 5 | `digital-twin/` panel in `apps/web-client` | §13 |
| 6 | Project-model reconstruction — the AC-6 path | §6.2, §16 |
| 7 | CI: `real-infra-checks` entry, import-linter contract, compose service already exists | §15 |

### 1.1 What 4E deliberately does **not** build

Named so their absence is disclosed rather than silently narrowed, per protocol
principle 0.3.6:

- **`nova-companion` and per-platform OS sensors** — 4F, by the roadmap's own
  assignment. 4E consumes whatever Perception has; it does not produce it.
- **`cognitive-state-engine`** — 4F.
- **The five Phase 5 panels** (`memory-timeline/`, `knowledge-graph/`,
  `world-model/`, `personality/`, `executive/`) — master scope §13.
- **Part 16's Workflow Model and Context Model sections beyond what the nine
  domains require** — Part 16 §§323, 379 describe more than a domain record.
- **Export/import profile, disable-domains, reset-domain** (Part 16 §§463–535)
  beyond what §7's table names.
- **Enterprise organization models** (Part 16 §641) — explicitly future.
- **Any autonomy behaviour.** 4E writes no policy, proposes no suggestion, and
  touches nothing in `autonomy-engine`.

---

## 2. Non-goals

Inherited from master scope §13 and restated:

- **No new model provider.** 4E adds none and does not resolve AC-4's deferred
  clauses.
- **Multi-user support or RBAC of any kind.** ADR-025's single-trusted-user model
  is preserved exactly.
- **Permission-derived subscription allow-lists.** Phase 4's allow-list stays a
  fixed, bounded list.
- **Phase 5 work of any kind.**

---

## 3. Dependencies and inherited state

### 3.1 Hard dependencies — all verified present at `phase-4` head `76a9662`

| Dependency | Verified state | Why 4E needs it |
|---|---|---|
| 4D merged into `phase-4` | `68397a2`; closure `76a9662` | §16 rule 5 — 4E branches from the merged head |
| `digital-twin-engine` (2D-D) | 9 ORM tables, 6 HTTP routes, outbox worker, 2 migrations | The engine 4E extends |
| `memory-engine` (Phase 1) | `MemoryRecord` with **`project_id: UUID \| None`**; `GET /search`, `/timeline`, `/{id}`; `memory.long_term.created` et al. | §5.2 — the primary evidence source, and the only place a project identity exists |
| `perception-engine` (2D-B) | 7 published subjects, `identity_observation` table, 4 route groups | §5.1 — the secondary evidence source |
| `api-gateway` route table (4A, D-6) | forwards 1:1; **no `/v1/digital-twin` entry yet** | §7 — 4E adds the entry |
| `ws-gateway` `PUBLIC_TOPICS` | **18 exact strings**, incl. 3 `perception.*`; **no `digital_twin.*`** | §10 — see §8 before assuming a realtime edge |
| `apps/web-client` shell, `entities/`, `realtime/` | shipped | The panel is a route, not new infrastructure |

### 3.2 Authoritative decisions this TDD is bound by

| Decision | Effect on 4E |
|---|---|
| **D-3** | Single long-lived local session validated by `api-gateway`. 4E introduces no second identity concept |
| **D-6** | `api-gateway` forwards 1:1, no path rewriting. 4E's paths are the shipped paths |
| **D-7** | The web app is the correct first UI |
| **ADR-025** | Single trusted user per instance |
| **ADR-030** | **Personality stores, Digital Twin learns** — binding on §6's boundary table |
| **ADR-004 / ADR-006** | Engines are independent; no engine imports another's internals; `ws-gateway` is the sole realtime bridge |
| **ADR-033** | Two-tier testing; `real_infra` marker; 85% domain coverage |

**D-1, D-2, D-4, D-5, D-8 and D-4D-1/D-4D-2 are other milestones' decisions.**
This document neither reinterprets nor extends them.

### 3.3 Carry-forwards that touch 4E — none closed here

| ID | Effect on 4E |
|---|---|
| **CF-9** | **OPEN, untouched.** No identity-confidence policy write path. 4E adds no gating and does not close it |
| **CF-10** | **OPEN, and 4E is the natural place to resolve it — but only by explicit decision.** `autonomy-engine` needs a `TrustMetric` read surface; `digital-twin-engine` owns `TrustMetric` and is being extended here. **This TDD does not create one.** Whether 4E adds it is a scope question for ratification (§19.2) |
| **CF-11** | **OPEN, untouched.** No production suggestion producer. 4E creates none |
| **CF-4** | Phase 3E narrowings — unaffected |
| **CF-5** | `PHR-1`/`PHR-2` — unaffected |
| **CF-6** | Real-Postgres verification of `perception-engine`'s repository layer still pending. 4E reads Perception evidence and should not be read as closing it |

---

## 4. The eleven domains, and the nine 4E adds

Bible Part 16 §§71–95 names eleven domains verbatim. Their shipped state was
verified against `services/digital-twin-engine` at `76a9662`:

| # | Part 16 domain | State | Evidence |
|---|---|---|---|
| 1 | **Personal Workflow** | **4E** | — |
| 2 | **Projects** | **4E** | — |
| 3 | **Software Environment** | **4E** | — |
| 4 | **Hardware Environment** | **4E** | — |
| 5 | **Knowledge Profile** | **4E** | — |
| 6 | **Skill Profile** | **4E** | — |
| 7 | **Communication Style** | **SHIPPED 2D-D** | `CommunicationProfileORM`; `GET/PATCH /profile`; `POST /reset` |
| 8 | **Productivity Patterns** | **4E** | — |
| 9 | **Goals** | **4E** | — |
| 10 | **Preferences** | **SHIPPED 2D-D** | `PreferenceEvolutionHistoryORM`; `digital_twin.preferences.get.request`; `GET /preferences` |
| 11 | **Learning Progress** | **4E** | — |

**Nine remain, and 11 − 2 = 9 closes exactly.** Part 16's names are used
verbatim, as 4D used Part 14's — no domain is renamed, merged or invented.

---

## 5. Evidence sources — what is real, and what is absent

**The binding rule, from Part 16 §69:** *"Never create assumptions without
evidence."* Every domain below names the repository surface it derives from. A
domain with no available evidence is **reported empty with its reason**, never
defaulted and never inferred.

### 5.1 Perception — real subjects, no autonomous producer until 4F

`perception-engine` publishes seven subjects, all real and all already consumed
by `world-model-engine` and/or `memory-engine`:

`perception.presence.observed` · `perception.identity.observed` ·
`perception.attention.observed` · `perception.wake.detected` ·
`perception.addressee_signal.candidate` · `perception.consent.changed` ·
`perception.sensor.health_changed`

**What 4E may use them for:** `Productivity Patterns` and `Personal Workflow`
(when the user is present and attentive, over time).

**The limitation, stated plainly (§0.1.4):** the only ingress is
`POST /v1/perception/observations`. `nova-companion` does not exist and is 4F's.
So in a stock deployment these subjects fire only when something posts an
observation. **Both affected domains must therefore report `NO_DATA` with a
reason, exactly as 4D's trust input reports `UNAVAILABLE`** — see §12.

### 5.2 Memory — the primary source, and the only place a project exists

`memory-engine` is the richer and more immediately usable source.

| Surface | Kind | What 4E derives |
|---|---|---|
| **`MemoryRecord.project_id: UUID \| None`** | field, shipped | **`Projects` — this is AC-6's entire basis.** The only project identity in the repository |
| `MemoryRecord.memory_type` (episodic, procedural, preference, decision…) | field, shipped | `Personal Workflow`, `Learning Progress` |
| `GET /v1/memories/search`, `/timeline` | HTTP, shipped | Bounded reads for reconstruction |
| `GET /v1/decisions/search`, `/{id}` | HTTP, shipped | `Goals`, `Knowledge Profile` |
| `memory.long_term.created` / `.updated`, `memory.decision.recorded`, `memory.lifecycle.transitioned` | subjects, shipped with real publishers | Incremental domain updates |

**`project_id` already exists and is already persisted.** 4E does not add a
project table to `memory-engine`, does not invent a project registry, and does
not write to Memory at all — it **reads**.

### 5.3 Domains with no identified evidence source

Honest accounting, because §0.1's rule forbids filling these by assumption:

| Domain | Evidence available today | Disposition |
|---|---|---|
| `Software Environment` | **None.** No engine reports installed tooling | **Modelled, reported empty with reason.** Its populator is 4F's `nova-companion` |
| `Hardware Environment` | **None.** Same | **Modelled, reported empty with reason** |
| `Skill Profile` | Partial — inferable from `memory_type=procedural` density | **Derived where evidence exists; empty otherwise** |
| `Knowledge Profile` | Partial — `knowledge_node_id` on `MemoryRecord` | **Derived where evidence exists; empty otherwise** |

**Four of the nine domains ship as a modelled-but-unpopulated surface.** That is
a disclosure, not a narrowing: the domain records exist, the API returns them,
and each states why it is empty. **This must be ratified (§19.1)** rather than
discovered at Gate Review.

---

## 6. Ownership boundaries

### 6.1 The binding table

| Concern | Owner | 4E's access |
|---|---|---|
| Raw memories, `project_id`, decisions | **`memory-engine`** | **Read-only**, via its HTTP surface and published subjects. Never its tables |
| Raw observations, identities, consent | **`perception-engine`** | **Read-only**, via its published subjects. Never its tables |
| Stored personality traits | **`personality-engine`** | **None.** ADR-030: *Personality stores, Digital Twin learns* |
| Derived domain models, their provenance | **`digital-twin-engine`** | **Owns** — new tables in its own schema |
| Realtime transport to the browser | **`ws-gateway`** | See §8 — 4E adds no topic |
| HTTP edge | **`api-gateway`** | Forwards `/v1/digital-twin` 1:1 (D-6) |
| Rendering | **`apps/web-client`** | Reads the REST surface; derives nothing |

**Import-linter enforces the first four rows mechanically** (ADR-004). 4E adds a
contract for `nova_digital_twin_engine` if one is not already present.

### 6.2 The AC-6 path, end to end

```
memory-engine  ──GET /v1/memories/search?project_id=…──▶  digital-twin-engine
                                                                  │
                                              ProjectModel derivation (§9)
                                                                  │
browser ──▶ api-gateway ──/v1/digital-twin/domains/projects/{id}──▶  ──┘
```

No Event Bus edge, no new subject, and no write back into Memory.

---

## 7. API contracts — defined before implementation

All on `digital-twin-engine`, forwarded 1:1 by `api-gateway` under
`/v1/digital-twin` (D-6). **Existing routes are unchanged**; these are additive.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/digital-twin/domains` | All eleven domains: name, populated/empty, last-derived, reason-if-empty |
| `GET` | `/v1/digital-twin/domains/{domain}` | One domain's current model + provenance |
| `POST` | `/v1/digital-twin/domains/{domain}/refresh` | Re-derive one domain from its sources. Explicit, user-triggered |
| `GET` | `/v1/digital-twin/domains/projects` | The project list derived from `MemoryRecord.project_id` |
| `GET` | `/v1/digital-twin/domains/projects/{project_id}` | **The AC-6 route** — the reconstruction |

**Five routes, no more.** Each exists because §13's panel or §16's AC-6 mapping
needs it. `POST /refresh` is the only write, and it writes only
`digital-twin-engine`'s own derived state.

**Schema discipline:** every request/response model is Pydantic with
`extra="forbid"`, matching 4D.

---

## 8. Event and realtime behaviour

### 8.1 Subscriptions — additive, and only where a real publisher exists

`digital-twin-engine` today subscribes to `communication.session.completed` and
serves `digital_twin.preferences.get.request`. 4E proposes adding to
`SUBSCRIBABLE_SUBJECTS` **only** subjects with verified real publishers:

| Subject | Real publisher | Domain served |
|---|---|---|
| `memory.long_term.created` | `memory-engine` | Projects, Personal Workflow |
| `memory.decision.recorded` | `memory-engine` | Goals |
| `perception.attention.observed` | `perception-engine` | Productivity Patterns *(subject to §5.1's producer limitation)* |

**No new subject is registered in `nova-contracts`.** All three already exist and
are already published. 4E is a **new consumer of existing contracts**, which is
precisely the relationship D-4D-1's governing principle requires: *do not
introduce an Event Bus contract without a genuine producer/consumer need.*

### 8.2 Publication — none

4E publishes **no** new subject. No `digital_twin.*` subject beyond the one
already served is claimed, registered or published.

### 8.3 Browser realtime — none

**`PUBLIC_TOPICS` stays at its 18 exact strings.** No `digital_twin.*` entry is
added. The panel reads REST and refreshes explicitly, because the Digital Twin
is a slowly-evolving derived model, not a live event stream — the same reasoning
D-4D-1 applied to autonomy suggestions.

---

## 9. Persistence

New tables in `digital-twin-engine`'s own schema, one migration, additive to the
existing two:

| Table | Purpose |
|---|---|
| `domain_model` | One row per Part 16 domain: name, populated flag, derived-at, empty-reason |
| `domain_evidence` | Provenance — which source record produced which derivation |
| `project_model` | The derived project record keyed by `memory-engine`'s `project_id` |

**`domain_evidence` is what makes Part 16 §69 enforceable**: every populated
field traces to a source record, and a domain with no evidence rows is empty by
construction rather than by convention.

**Alembic:** a new revision on the engine's existing chain, with its own
`version_table` as established across all engines.

---

## 10. Security boundaries

Unchanged from the shipped posture; 4E weakens nothing.

1. **ADR-025 single trusted user.** No second identity concept, no RBAC.
2. **`ws-gateway` remains the sole realtime bridge**, and `PUBLIC_TOPICS` is
   byte-identical at 18 strings.
3. **`/internal/*` is not routable through `api-gateway`.**
4. **No cross-engine table access.** Memory and Perception are read through their
   own published surfaces only.
5. **Privacy.** `MemoryRecord.privacy_level` is respected on read; a derivation
   must not surface a memory the user marked private through a domain the panel
   renders. **This needs a stated rule (§19.3).**

---

## 11. Provider-dependent versus provider-free

| Behaviour | Provider needed? |
|---|---|
| Deriving `Projects` from `project_id`, and the AC-6 reconstruction | **No** — deterministic grouping over persisted rows |
| `Goals`, `Learning Progress`, `Personal Workflow` from memory types | **No** — deterministic |
| Semantic clustering or natural-language summarisation of a project | **Yes** — and it is therefore **out of 4E's scope** |
| `Productivity Patterns` from Perception | **No provider**, but **no autonomous producer** either (§5.1) |

**AC-6 is provider-free and does not inherit AC-4's deferral.** The
reconstruction is a query over persisted rows, not a generated narrative.

---

## 12. Domain evidence states — ratified 2026-09-14

**Four states, not three.** The three-state model this section first proposed
(borrowed from 4D's `TrustInputStatus`) could not express a domain that is
genuinely half-derived, which `Knowledge Profile` and `Skill Profile` are. The
ratified model adds `partially_populated`:

| State | Meaning | Reason required? |
|---|---|---|
| `populated` | Evidence exists and the domain was fully derived from it | No |
| `partially_populated` | Some fields derived from real evidence; the rest have none | **Yes** |
| `empty` | The source exists and was queried; it returned nothing | **Yes** |
| `unavailable` | The source could not be reached | **Yes** |

**Every `partially_populated`, `empty` and `unavailable` state carries a
machine-readable reason** — an enumerated code plus human-readable detail, not
free text alone, so the panel can render it and a test can assert it.

**Fail-empty, never fail-plausible.** A domain that cannot be derived reports its
state and reason — never a default, a zero, an average, or an inferred value.
This is Part 16 §69 (*"Never create assumptions without evidence"*) expressed as
a type, and §14.5 control 5 makes it unrepresentable to report `populated`
without evidence rows.

**Binding per-domain floor (ratified §19.1):**

| Domain | Permitted states in 4E |
|---|---|
| `Software Environment` | **`empty` or `unavailable` only** — no real source exists until 4F |
| `Hardware Environment` | **`empty` or `unavailable` only** — same |
| `Knowledge Profile` | `partially_populated` at most, **and only from real existing data** |
| `Skill Profile` | `partially_populated` at most, **and only from real existing data** |
| The other five | `populated` where real evidence supports it |

**No Digital Twin data is fabricated** for any domain, in any state.

---

## 13. The `digital-twin/` panel

Master scope §6 assigns `digital-twin/` to 4E against
`digital-twin-engine /v1/digital-twin`.

| Widget | Source |
|---|---|
| Domain overview — eleven domains, populated/empty, reason | `GET /domains` |
| Domain detail | `GET /domains/{domain}` |
| Project list | `GET /domains/projects` |
| **Project reconstruction — the AC-6 surface** | `GET /domains/projects/{id}` |
| Refresh control | `POST /domains/{domain}/refresh` |

Conventions carried from 4D: strict Zod parsing of every response, mutations
**invalidate and re-read** rather than patching the cache optimistically, no
polling, and no fabricated runtime data. An empty domain renders its reason.

---

## 14. Testing

### 14.1 Unit
Domain derivation is pure: source records in, domain model out. 85% domain
coverage (ADR-033).

### 14.2 Integration
The five routes against a `TestClient` with faked repositories and faked source
clients, including every `NO_DATA` and `UNAVAILABLE` path.

### 14.3 Real-Postgres (`real_infra`)
A `real-infra-checks.yml` matrix entry for `digital-twin-engine` — **master scope
§15 assigns one to 4D and 4F; 4E needs its own, and §15's table does not list it
(§19.4).** Coverage: the three new tables, the `domain_evidence` foreign key, and
the project-model round trip.

### 14.4 Browser / E2E — AC-6
A Playwright spec asserting the full chain against the real stack:

1. Seed memories with real past `created_at` values through the **real**
   `POST /v1/memories` route (§0.1.3's proposed simulation, pending ratification).
2. Open the panel, navigate to the project.
3. Assert the reconstruction renders what was seeded — and **nothing more**.
4. Assert an unpopulated domain renders its reason, not a zero.

### 14.5 Negative and security controls
Each demonstrated by removing the property and observing a named test fail — 4D's
standard, not a declaration:

1. **No new Event Bus subject is registered** by this engine.
2. **`PUBLIC_TOPICS` is byte-identical** at its 18 exact strings.
3. **No cross-engine import** — import-linter, plus an AST check.
4. **No write to `memory-engine` or `perception-engine`.**
5. **A domain with no evidence rows cannot report `populated`** — and
   `Software Environment` / `Hardware Environment` cannot report anything but
   `empty` or `unavailable` (§12's floor, ratified §19.1).
6. **A `PRIVATE` memory never reaches a rendered domain** — ratified §19.3.
   Written through the real path, every domain derived, no rendered field carries
   its content.
7. **Only the five §7 routes are published**, asserted against the OpenAPI document.
8. **No `autonomy.*` subject and no autonomy behaviour** is introduced.
9. **CF-10 is not resolved by 4E** — ratified §19.2, asserted as five separate
   properties: no `TrustMetric` REST route, no `TrustMetric` Event Bus subject,
   no `TrustMetric` RPC, `autonomy-engine`'s trust adapter byte-identical, and
   its fail-closed behaviour unchanged (`score` is `None` never `0.0`;
   `satisfies_threshold(None, t)` `False` for every `t` including `0.0`).
10. **Every non-`populated` state carries a machine-readable reason** — a domain
    reporting `partially_populated`, `empty` or `unavailable` without an
    enumerated reason code fails.

---

## 15. CI requirements

Additive; no existing job is weakened.

| Workflow | Addition |
|---|---|
| `real-infra-checks.yml` | `digital-twin-engine` entry (§19.4) |
| `build-and-scan.yml` | **None** — `digital-twin-engine` is already in the matrix |
| `pr-checks.yml` | The AC-6 Playwright spec joins the existing golden-path job |
| `.importlinter` | Contract for `nova_digital_twin_engine` if absent |

The engine's Dockerfile already carries the runtime-hardening convention
(20 of 20 images, post-PR #28), and `tools/tests/test_dockerfile_runtime_hardening.py`
keeps it that way.

---

## 16. Explicit mapping to AC-6

> **AC-6** — *"The Digital Twin's project model correctly reconstructs 'what was
> I doing on Project X' after a simulated multi-week gap, and the reconstruction
> is visible in the Digital Twin panel."*

| Clause | Discharged by | Proof |
|---|---|---|
| *"The Digital Twin's project model"* | `project_model`, derived from `MemoryRecord.project_id` | Unit test over real record shapes |
| *"correctly reconstructs 'what was I doing on Project X'"* | `GET /domains/projects/{id}` | Integration + real-Postgres round trip |
| *"after a simulated multi-week gap"* | Past-dated memories through the real write path | §14.4 — **mechanism pending ratification (§0.1.3)** |
| *"visible in the Digital Twin panel"* | The reconstruction widget | Playwright, in a browser, against the real stack |

**AC-6 is provider-free** and inherits no deferral.

---

## 17. SLOC and repository hygiene gates

- **`cloc` v2.06, `--skip-uniqueness --quiet`, measured from a pristine
  `git archive` extract.** Phase 4D's Gate Review §22.6 records why: measuring a
  working tree produced figures **56 low** at both endpoints.
- Three scopes reported side by side, continuing 4C.2's and 4D's shape.
- **50,000 SLOC remains uncrossed** — 4D closed at 34,469 comparable / 43,114
  full. 4E should re-check, since a nine-domain extension is substantial.
- Branch hygiene: `phase-4e` cut from the merged `phase-4` head per §16 rule 5,
  preserved not deleted, no rebase, no force-push, no squash.

---

## 18. Compatibility with the Bible

| Part 16 section | 4E |
|---|---|
| Domain list (§§71–95) | **All eleven named verbatim**; nine added, two already shipped |
| *"Never create assumptions without evidence"* (§69) | `domain_evidence` makes it structural; §12 makes an unevidenced domain unrepresentable as populated |
| Goal / Project / Productivity / Software / Hardware / Skill / Knowledge models (§§123–301) | The nine domains |
| Communication Profile (§303) | **Unchanged** — 2D-D's, untouched |
| Workflow Model (§323), Context Model (§379) | **Beyond 4E** — §1.1 |
| Export / import / disable domains (§§463–535) | **Beyond 4E** — §1.1 |
| Enterprise organization models (§641) | Explicitly future |

---

## 19. Ratified decisions — 2026-09-14

This section was written as five open questions and is **replaced by the user's
ratification of 2026-09-14**. Each original question and its recommendation is
preserved inline, per protocol §0.3.4; what changed is that each now has a
binding answer. **Implementation may proceed on these terms and no others.**

### 19.1 Empty domains — **APPROVED**

**All nine remaining domains are delivered as modelled domains with an explicit
evidence state. A domain does not need fabricated data to count as delivered.**

The four states are `populated`, `partially_populated`, `empty` and
`unavailable` (§12), and **every non-`populated` state exposes a
machine-readable reason**.

- `Software Environment` and `Hardware Environment` **remain `empty` or
  `unavailable` until a real Phase 4F source exists.**
- `Knowledge Profile` and `Skill Profile` **may be `partially_populated` only
  from real existing data.**
- **No Digital Twin data is fabricated**, in any domain or any state.

*(Asked as: whether the four evidence-less domains ship as empty surfaces, defer
to 4F, or get a populator — the third rejected as inventing a data source.
Recommended (a), ship them modelled-and-empty. Approved, with the four-state
model and the per-domain floor in §12 replacing the looser three-state proposal.)*

### 19.2 CF-10 — **APPROVED AS OUT OF SCOPE**

**Phase 4E must not resolve CF-10. CF-10 stays OPEN.** Binding prohibitions:

- **No `TrustMetric` REST route.**
- **No `TrustMetric` Event Bus subject.**
- **No `TrustMetric` RPC.**
- **No modification to `autonomy-engine`'s trust adapter.**
- **The existing fail-closed behaviour is preserved** — score `None` and never
  `0.0`, `satisfies_threshold(None, t)` `False` for every `t` including `0.0`.

§14.5 gains a control asserting all five (control 9).

*(Asked as: whether 4E resolves CF-10, given that `digital-twin-engine` owns
`TrustMetric` and is open for extension here. Recommended out of scope.
Approved.)*

### 19.3 Privacy — **APPROVED**

**Memory records marked `PRIVATE` must not contribute to rendered Digital Twin
domain data.** An explicit negative control proves it (§14.5 control 6):
a `PRIVATE` memory is written through the real path, every domain is derived,
and no rendered field carries its content.

**The underlying Memory privacy model is not changed** — `MemoryRecord.privacy_level`
keeps its current semantics, and 4E filters on read.

*(Asked as: what the privacy rule is for derived domains, since none was stated.
Recommended excluding `PRIVATE`. Approved.)*

### 19.4 Real-infrastructure verification — **APPROVED**

**4E includes real-Postgres verification for the Digital Twin reconstruction and
persistence path**, using **the repository's existing conventions** — the
`real_infra` pytest marker (ADR-033), `nova-testkit`'s container fixtures, and a
`real-infra-checks.yml` matrix entry. **No new CI framework.**

**The test exercises real persisted rows and the real Digital Twin read path.**
The repository and database layers are **not** replaced with mocks; the fake
repository used in §14.2's integration tier is explicitly not permitted here.

An additive correction to master scope §15 records the matrix entry, since its
table assigns `real-infra-checks.yml` entries to "the two new engines" (4D, 4F)
and 4E extends an existing one.

*(Asked as: §15 lists no `real-infra` entry for 4E. Recommended adding one.
Approved.)*

### 19.5 TDD landing — **APPROVED, with the flow below**

`phase-4e-tdd` is a **preparation branch**. The ratified flow:

1. **Land the approved TDD and documentation into `phase-4`** — a normal
   two-parent merge, no squash, no rebase, no force-push.
2. **Then create `phase-4e` from the updated `phase-4` HEAD**, satisfying master
   scope §16 rule 5 so the milestone branch inherits its own TDD — the same
   relationship `eedb8ad` had to `phase-4d`.
3. **Then perform all Phase 4E implementation on `phase-4e`.**

**No Phase 4E implementation on `phase-4e-tdd`. `phase-4e` is not created until
the TDD is landed in `phase-4`. `main` is not modified.**

*(Asked as: where this TDD should be committed, given that precedent puts a TDD
on `phase-4` but the authorising instruction forbade all three in-repo targets.
Recommended landing on `phase-4` before `phase-4e` is cut. Approved.)*
